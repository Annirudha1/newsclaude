from django.core.management.base import BaseCommand
from news.models import RSSSource


class Command(BaseCommand):
    help = 'Add new RSS feeds to the database'

    def handle(self, *args, **options):
        feeds_to_add = [
            {   
                'feed_name': 'Sports Feed 1',
                'feed_url': 'https://rss.app/feeds/v1.1/W1xMVHKkbpIIwPbI.json',
                'category': 'sports',
            },
            {
                'feed_name': 'Education feed 2',
                'feed_url': 'https://rss.app/feeds/v1.1/tcB9grcMvoS8vkSm.json',
                'category': 'education',
            },
            {
                'feed_name': 'Technology Feed 3',
                'feed_url': 'https://rss.app/feeds/v1.1/cOILu2iUHPxHIlT1.json',
                'category': 'technology',
            },
             {
                'feed_name': 'health Feed 5',
                'feed_url': 'https://rss.app/feeds/v1.1/tZABHYWSggoUkDz8.json',
                'category': 'health',
            },
             {
                'feed_name': 'business Feed 6',
                'feed_url': 'https://rss.app/feeds/v1.1/tnVpoLMc9TOQB91R.json',
                'category': 'business',
            },
            {
                'feed_name': 'science Feed 7',
                'feed_url': 'https://rss.app/feeds/v1.1/t4ESdsDCX19L3WJZ.json',
                'category': 'science',
            },
        ]    

        for feed in feeds_to_add:
            # Check if feed already exists
            if RSSSource.objects.filter(feed_url=feed['feed_url']).exists():
                self.stdout.write(
                    self.style.WARNING(f"⚠️  Feed already exists: {feed['feed_name']}")
                )
            else:
                rss_source = RSSSource.objects.create(
                    feed_name=feed['feed_name'],
                    feed_url=feed['feed_url'],
                    category=feed['category'],
                    is_active=True
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Added: {feed['feed_name']} ({feed['category']})")
                )

        self.tdout.write(self.style.SUCCESS('\n✓ All feeds have been processed!'))
