"""RSS import services shared by the scheduler, command, and admin action."""

from datetime import datetime, timedelta

import feedparser
import requests
from dateutil import parser as date_parser
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Article, RSSSource, Short, YouTubeChannel


def fetch_active_sources():
    """Fetch every active source and return the number of newly saved articles."""

    created = sum(
        fetch_source(source)
        for source in RSSSource.objects.filter(is_active=True)
    )

    # Delete articles older than 7 days
    cutoff = timezone.now() - timedelta(days=7)
    Article.objects.filter(created_at__lt=cutoff).delete()

    return created


def fetch_active_shorts():
    """Generate YouTube channel feeds and merge their newest videos into Shorts."""
    return sum(fetch_shorts_from_channel(channel) for channel in YouTubeChannel.objects.filter(is_active=True))


def fetch_shorts_from_channel(channel):
    """Import one channel's generated YouTube RSS feed without storing an RSS URL."""
    feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel.channel_id}'
    feed = feedparser.parse(feed_url)
    created = 0

    for entry in feed.entries[:30]:
        video_id = entry.get('yt_videoid') or _youtube_video_id(entry.get('link', ''))
        if not video_id or Short.objects.filter(video_id=video_id).exists():
            continue

        try:
            with transaction.atomic():
                Short.objects.create(
                    channel=channel,
                    video_id=video_id,
                    title=(entry.get('title') or 'Untitled Short')[:300],
                    description=entry.get('summary', '')[:1000],
                    thumbnail_url=_youtube_thumbnail(entry, video_id),
                    published_at=_parse_date(entry.get('published') or entry.get('updated')),
                )
            created += 1
        except IntegrityError:
            # A different scheduler worker already imported this video.
            continue

    channel.last_fetched = timezone.now()
    if created:
        channel.shorts_count += created
    channel.save(update_fields=['last_fetched', 'shorts_count', 'updated_at'])
    return created


def fetch_source(source):
    """Import one source, assigning every article to that source's category."""
    try:
        items = _json_items(source) if source.feed_url.lower().endswith('.json') else _rss_items(source)
        created = sum(_save_item(source, item, is_json=source.feed_url.lower().endswith('.json')) for item in items[:30])
    except Exception:
        raise
    else:
        source.last_fetched = timezone.now()
        if created:
            source.articles_count += created
        source.save(update_fields=['last_fetched', 'articles_count', 'updated_at'])
        return created


def _json_items(source):
    response = requests.get(source.feed_url, timeout=15)
    response.raise_for_status()
    return response.json().get('items', [])


def _rss_items(source):
    feed = feedparser.parse(source.feed_url)
    return feed.entries


def _save_item(source, item, *, is_json):
    url = (item.get('url') or item.get('link') or '').strip()
    if not url or Article.objects.filter(source_url=url).exists():
        return 0

    if is_json:
        raw_date = item.get('date_published')
        image_url = item.get('image', '')
        description = item.get('summary') or item.get('content_text', '')
    else:
        raw_date = item.get('published') or item.get('updated')
        image_url = _rss_image(item)
        description = item.get('summary', '')

    try:
        published_at = _parse_date(raw_date)
        with transaction.atomic():
            Article.objects.create(
                title=(item.get('title') or 'Untitled')[:300],
                image_url=image_url or '',
                source_url=url,
                published_at=published_at,
                description=description[:500],
                category=source.category,
                # Imported stories are visible to the site immediately.
                is_published=True,
                status='published',
            )
    except IntegrityError:
        # source_url is unique: another scheduler/worker already imported it.
        return 0
    return 1


def _rss_image(item):
    for key in ('media_thumbnail', 'media_content'):
        values = item.get(key) or []
        if values:
            return values[0].get('url', '')
    return ''


def _parse_date(value):
    if not value:
        return timezone.now()
    try:
        parsed = date_parser.parse(value) if isinstance(value, str) else datetime(*value[:6])
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except (TypeError, ValueError, OverflowError):
        return timezone.now()


def _youtube_video_id(url):
    """Read a YouTube video ID from the standard RSS entry URL."""
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(url).query).get('v', [''])[0]


def _youtube_thumbnail(entry, video_id):
    thumbnails = entry.get('media_thumbnail') or []
    if thumbnails and thumbnails[0].get('url'):
        return thumbnails[0]['url']
    return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
