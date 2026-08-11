from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Article, CATEGORY_CHOICES, RSSSource, Short, YouTubeChannel


class CategoryFilter(admin.SimpleListFilter):
    """Filter admin changelists by an explicit, valid article/feed category."""

    title = 'category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        return CATEGORY_CHOICES

    def queryset(self, request, queryset):
        category = self.value()
        valid_categories = {value for value, _label in CATEGORY_CHOICES}
        if category in valid_categories:
            return queryset.filter(category=category)
        return queryset


@admin.register(YouTubeChannel)
class YouTubeChannelAdmin(admin.ModelAdmin):
    """Channel IDs are the only source information an editor needs to provide."""

    list_display = ('channel_id', 'is_active', 'shorts_count', 'last_fetched')
    list_filter = ('is_active',)
    search_fields = ('channel_id',)
    readonly_fields = ('shorts_count', 'last_fetched', 'created_at', 'updated_at')

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('channel_id',)
        return ('channel_id', 'is_active', 'shorts_count', 'last_fetched', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not obj.is_active:
            return

        from .services import fetch_shorts_from_channel

        try:
            created = fetch_shorts_from_channel(obj)
            self.message_user(request, f'{created} new Short(s) imported from {obj.channel_id}.')
        except Exception as exc:
            self.message_user(request, f'Could not fetch {obj.channel_id}: {exc}', level=messages.ERROR)


@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'video_id', 'published_at', 'delete_link')
    list_filter = ('channel', 'published_at')
    search_fields = ('title', 'video_id')
    readonly_fields = ('channel', 'video_id', 'title', 'description', 'thumbnail_url', 'published_at', 'created_at')

    def delete_link(self, obj):
        return format_html(
            '<a href="{}" style="color: #dc2626; font-weight: 600;">Delete</a>',
            reverse('admin:news_short_delete', args=[obj.pk]),
        )
    delete_link.short_description = 'Delete'


@admin.register(RSSSource)
class RSSSourceAdmin(admin.ModelAdmin):
    """Admin interface for managing RSS feed sources"""
    list_display = ('feed_name_with_status', 'category_badge', 'rss_url_link', 'articles_count', 'last_fetched', 'active_badge')
    list_filter = ('is_active', CategoryFilter, 'created_at', 'last_fetched')
    search_fields = ('feed_name', 'feed_url')
    readonly_fields = ('articles_count', 'last_fetched', 'created_at', 'updated_at')
    
    fieldsets = (
        ('RSS Feed Information', {
            'fields': ('feed_name', 'feed_url', 'category', 'is_active'),
            'description': 'Configure the RSS feed source'
        }),
        ('Feed Statistics', {
            'fields': ('articles_count', 'last_fetched', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_feeds', 'deactivate_feeds', 'fetch_now']
    list_per_page = 20
    date_hierarchy = 'created_at'
    
    def feed_name_with_status(self, obj):
        """Display feed name with status indicator"""
        status_icon = '🟢' if obj.is_active else '🔴'
        return format_html(
            '{} <strong>{}</strong>',
            status_icon,
            obj.feed_name
        )
    feed_name_with_status.short_description = 'Feed Name'
    
    def category_badge(self, obj):
        """Display category as colored badge"""
        colors = {
            'technology': '#3b82f6',
            'business': '#f97316',
            'sports': '#22c55e',
            'health': '#ef4444',
            'science': '#8b5cf6',
            'education': '#06b6d4',
            'trending': '#ea580c',
            'home': '#6366f1'
        }
        color = colors.get(obj.category, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 16px; font-size: 11px; font-weight: 600;">{}</span>',
            color,
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'
    
    def feed_url_link(self, obj):
        """Display feed URL as clickable link"""
        return format_html(
            '<a href="{}" target="_blank" style="color: #2563eb; text-decoration: none;">🔗 View Feed</a>',
            obj.feed_url
        )
    feed_url_link.short_description = 'Feed URL'

    def rss_url_link(self, obj):
        """Display a safe link to the RSS resource."""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none;">Open RSS feed</a>',
            obj.feed_url,
        )
    rss_url_link.short_description = 'Feed URL'
    
    def last_fetched_display(self, obj):
        """Display last fetch time with status"""
        if obj.last_fetched:
            return format_html(
                '<span style="color: #16a34a;">✓ {}</span>',
                obj.last_fetched.strftime('%Y-%m-%d %H:%M')
            )
        return format_html('<span style="color: #999;">Never</span>')
    last_fetched_display.short_description = 'Last Fetched'
    
    def active_badge(self, obj):
        """Display active status as badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #16a34a; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px;">🟢 ACTIVE</span>'
            )
        return format_html(
            '<span style="background-color: #ef4444; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px;">🔴 INACTIVE</span>'
        )
    active_badge.short_description = 'Status'

    def active_badge(self, obj):
        """Display feed status without character-encoding dependent symbols."""
        label = 'Active' if obj.is_active else 'Inactive'
        color = '#16a34a' if obj.is_active else '#ef4444'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            label,
        )
    active_badge.short_description = 'Status'
    
    def activate_feeds(self, request, queryset):
        """Activate selected feeds"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} feed(s) activated successfully.')
    activate_feeds.short_description = '🟢 Activate selected feeds'
    
    def deactivate_feeds(self, request, queryset):
        """Deactivate selected feeds"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} feed(s) deactivated successfully.')
    deactivate_feeds.short_description = '🔴 Deactivate selected feeds'
    
    def fetch_now(self, request, queryset):
        """Fetch articles from selected feeds now"""
        try:
            import feedparser
        except ImportError:
            feedparser = None

        try:
            import requests
        except ImportError:
            requests = None

        import json
        from datetime import datetime
        from django.utils import timezone
        from dateutil import parser as date_parser
        from .models import Article

        if feedparser is None or requests is None:
            self.message_user(
                request,
                'Feed fetching requires the feedparser and requests packages.',
                level=messages.ERROR,
            )
            return
        
        total_fetched = 0
        for rss_source in queryset.filter(is_active=True):
            try:
                fetched_count = 0
                
                # Check if it's a JSON feed
                if rss_source.feed_url.endswith('.json'):
                    # Handle JSON Feed format
                    response = requests.get(rss_source.feed_url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    items = data.get('items', [])
                    
                    for item in items[:30]:
                        source_url = item.get('url', '') or item.get('link', '')
                        if not source_url:
                            continue
                        
                        if Article.objects.filter(source_url=source_url).exists():
                            continue
                        
                        try:
                            image_url = item.get('image', '')
                            published_at = timezone.now()
                            
                            if item.get('date_published'):
                                try:
                                    published_at = timezone.make_aware(
                                        date_parser.parse(item.get('date_published'))
                                    )
                                except (ValueError, TypeError):
                                    published_at = timezone.now()
                            
                            Article.objects.create(
                                title=item.get('title', 'Untitled')[:300],
                                image_url=image_url,
                                source_url=source_url,
                                published_at=published_at,
                                description=item.get('summary', '') or item.get('content_text', '')[:500],
                                category=rss_source.category,
                                status='draft',
                            )
                            fetched_count += 1
                        except Exception as e:
                            continue
                
                else:
                    # Handle RSS/Atom feed format
                    feed = feedparser.parse(rss_source.feed_url)
                    
                    for entry in feed.entries[:30]:
                        source_url = entry.get('link', '')
                        if not source_url:
                            continue
                        
                        if Article.objects.filter(source_url=source_url).exists():
                            continue
                        
                        try:
                            image_url = ''
                            if entry.get('media_thumbnail'):
                                image_url = entry.get('media_thumbnail')[0].get('url', '')
                            elif entry.get('media_content'):
                                image_url = entry.get('media_content')[0].get('url', '')
                            
                            published_at = timezone.now()
                            if entry.get('published_parsed'):
                                try:
                                    published_at = timezone.make_aware(
                                        datetime(*entry.get('published_parsed')[:6])
                                    )
                                except (ValueError, TypeError):
                                    published_at = timezone.now()
                            
                            Article.objects.create(
                                title=entry.get('title', 'Untitled')[:300],
                                image_url=image_url,
                                source_url=source_url,
                                published_at=published_at,
                                description=entry.get('summary', '')[:500],
                                category=rss_source.category,
                                status='draft',
                            )
                            fetched_count += 1
                        except Exception as e:
                            continue
                
                # Update feed statistics
                rss_source.last_fetched = timezone.now()
                rss_source.articles_count += fetched_count
                rss_source.save()
                total_fetched += fetched_count
                
                if fetched_count > 0:
                    self.message_user(request, f'✓ {rss_source.feed_name}: {fetched_count} new articles fetched')
                
            except Exception as e:
                self.message_user(
                    request,
                    f'Error fetching from {rss_source.feed_name}: {str(e)}',
                    level=messages.ERROR,
                )
        
        self.message_user(request, f'✓ Total: {total_fetched} new articles fetched from selected feeds.')
    fetch_now.short_description = '⚡ Fetch now from selected feeds'


    def fetch_now(self, request, queryset):
        """Fetch selected feeds using the same duplicate-safe importer as the scheduler."""
        from .services import fetch_source

        total_fetched = 0
        for rss_source in queryset.filter(is_active=True):
            try:
                fetched_count = fetch_source(rss_source)
                total_fetched += fetched_count
                self.message_user(request, f'{rss_source.feed_name}: {fetched_count} new article(s) imported.')
            except Exception as exc:
                self.message_user(
                    request,
                    f'Error fetching from {rss_source.feed_name}: {exc}',
                    level=messages.ERROR,
                )
        self.message_user(request, f'Total imported and published: {total_fetched} new article(s).')
    fetch_now.short_description = 'Fetch selected feeds now'


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('colored_title', 'category_badge', 'status_badge', 'trending_badge', 'published_badge', 'published_at', 'article_url_link', 'delete_link')
    list_filter = (CategoryFilter, 'is_trending', 'is_published', 'status', 'created_at')
    search_fields = ('title', 'description', 'source_url')
    
    fieldsets = (
        ('Article Content', {
            'fields': ('title', 'slug', 'description', 'image_url')
        }),
        ('Source & Publishing', {
            'fields': ('source_url', 'published_at', 'category')
        }),
        ('Status & Visibility', {
            'fields': ('status', 'is_published', 'is_trending'),
            'description': 'Control article visibility and features'
        }),
    )
    
    actions = ['publish_articles', 'unpublish_articles', 'mark_trending', 'remove_trending', 'mark_draft']
    list_per_page = 25
    date_hierarchy = 'published_at'
    readonly_fields = ('slug', 'created_at', 'updated_at')
    
    def colored_title(self, obj):
        """Display title with color based on status"""
        colors = {'draft': '#FF9800', 'published': '#4CAF50', 'archived': '#F44336'}
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
        )
    colored_title.short_description = 'Title'
    
    def category_badge(self, obj):
        """Display category as badge"""
        colors = {
            'technology': '#2196F3',
            'business': '#FF9800',
            'sports': '#4CAF50',
            'health': '#F44336',
            'science': '#9C27B0',
            'education': '#00BCD4',
        }
        color = colors.get(obj.category, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.get_category_display()
        )
    category_badge.short_description = 'Category'
    
    def status_badge(self, obj):
        """Display status as badge"""
        status_colors = {'draft': '#FF9800', 'published': '#4CAF50', 'archived': '#F44336'}
        color = status_colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def trending_badge(self, obj):
        """Display trending status"""
        if obj.is_trending:
            return mark_safe('<span style="background-color: #FF5722; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">🔥 TRENDING</span>')
        return mark_safe('<span style="color: #ccc;">—</span>')
    trending_badge.short_description = 'Trending'
    
    def published_badge(self, obj):
        """Display published status"""
        if obj.is_published:
            return format_html('<span style="color: #4CAF50; font-weight: bold;">✓ Published</span>')
        return format_html('<span style="color: #FF9800;">○ Draft</span>')
    published_badge.short_description = 'Published'

    def published_badge(self, obj):
        """Display status text without character-encoding dependent symbols."""
        label = 'Published' if obj.is_published else 'Draft'
        color = '#4CAF50' if obj.is_published else '#FF9800'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label,
        )
    published_badge.short_description = 'Published'

    def article_url_link(self, obj):
        """Display a safe link to the article's original source."""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none;">Open article</a>',
            obj.source_url,
        )
    article_url_link.short_description = 'Source'

    def delete_link(self, obj):
        return format_html(
            '<a href="{}" style="color: #dc2626; font-weight: 600;">Delete</a>',
            reverse('admin:news_article_delete', args=[obj.pk]),
        )
    delete_link.short_description = 'Delete'
    
    def publish_articles(self, request, queryset):
        """Publish selected articles"""
        updated = queryset.update(is_published=True, status='published')
        self.message_user(request, f'{updated} article(s) published successfully.')
    publish_articles.short_description = '✓ Publish selected articles'
    
    def unpublish_articles(self, request, queryset):
        """Unpublish selected articles"""
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} article(s) unpublished.')
    unpublish_articles.short_description = '○ Unpublish selected articles'
    
    def mark_trending(self, request, queryset):
        """Mark articles as trending"""
        updated = queryset.update(is_trending=True)
        self.message_user(request, f'{updated} article(s) marked as trending.')
    mark_trending.short_description = '🔥 Mark as trending'
    
    def remove_trending(self, request, queryset):
        """Remove trending status"""
        updated = queryset.update(is_trending=False)
        self.message_user(request, f'{updated} article(s) removed from trending.')
    remove_trending.short_description = '○ Remove from trending'
    
    def mark_draft(self, request, queryset):
        """Mark articles as draft"""
        updated = queryset.update(status='draft', is_published=False)
        self.message_user(request, f'{updated} article(s) marked as draft.')
    mark_draft.short_description = '⬜ Mark as draft'
