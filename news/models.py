from django.conf import settings
from django.db import models
from django.utils.text import slugify


CATEGORY_CHOICES = [
    ('home', 'Home'),
    ('technology', 'Technology'),
    ('business', 'Business'),
    ('education', 'Education'),
    ('sports', 'Sports'),
    ('health', 'Health'),
    ('science', 'Science'),
]


class Article(models.Model):
    title = models.CharField(max_length=300)
    image_url = models.URLField(blank=True)
    source_url = models.URLField(unique=True)
    published_at = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='home')
    is_trending = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='draft')
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:190] or 'article'
            slug = base_slug
            suffix = 2
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{suffix}'
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class YouTubeChannel(models.Model):
    """A YouTube channel used to generate and import its Shorts feed."""

    channel_id = models.CharField(max_length=64, unique=True, help_text='YouTube Channel ID (starts with UC)')
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    shorts_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-updated_at']

    def clean(self):
        super().clean()
        self.channel_id = self.channel_id.strip()
        # YouTube upload-playlist IDs use UU where the corresponding channel ID
        # uses UC. Accepting this common pasted value prevents a silent 404.
        if self.channel_id.startswith('UU'):
            self.channel_id = f'UC{self.channel_id[2:]}'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.channel_id


class Short(models.Model):
    """A duplicate-safe YouTube Short imported from a configured channel."""

    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE, related_name='shorts')
    video_id = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    @property
    def watch_url(self):
        return f'https://www.youtube.com/shorts/{self.video_id}'

    def __str__(self):
        return self.title


class ArticleLike(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('article', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} likes {self.article}'


class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_comments')
    body = models.TextField(max_length=2000)
    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user} on {self.article}'


class RSSSource(models.Model):
    """Model for managing RSS feed sources"""
    feed_name = models.CharField(max_length=255, help_text="Name of the RSS feed source")
    feed_url = models.URLField(unique=True, help_text="URL of the RSS feed")
    category = models.CharField(
        max_length=30, 
        choices=CATEGORY_CHOICES, 
        default='home',
        help_text="Category where articles from this feed will be imported"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="When unchecked, this feed will not be fetched"
    )
    last_fetched = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last successful fetch"
    )
    articles_count = models.IntegerField(
        default=0,
        help_text="Total articles imported from this feed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'RSS Source'
        verbose_name_plural = 'RSS Sources'
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return f"{self.feed_name} ({self.category}) {'🟢' if self.is_active else '🔴'}"
