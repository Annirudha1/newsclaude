from types import SimpleNamespace
from importlib import import_module
from unittest.mock import MagicMock, patch
from datetime import datetime

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .apps import NewsConfig
from .admin import ArticleAdmin, RSSSourceAdmin, ShortAdmin
from .models import Article, ArticleComment, RSSSource, Short, YouTubeChannel


class AdminCategoryFilterTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password',
        )
        self.client.force_login(user)
        self.categories = ('business', 'health', 'science')

        for category in self.categories:
            Article.objects.create(
                title=f'{category} article',
                source_url=f'https://example.com/{category}-article',
                category=category,
            )
            RSSSource.objects.create(
                feed_name=f'{category} feed',
                feed_url=f'https://example.com/{category}-feed.xml',
                category=category,
            )

    def test_article_category_filters_return_only_the_selected_category(self):
        url = reverse('admin:news_article_changelist')
        for category in self.categories:
            response = self.client.get(url, {'category': category})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                list(response.context['cl'].queryset.values_list('category', flat=True)),
                [category],
            )

    def test_rss_source_category_filters_return_only_the_selected_category(self):
        url = reverse('admin:news_rsssource_changelist')
        for category in self.categories:
            response = self.client.get(url, {'category': category})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                list(response.context['cl'].queryset.values_list('category', flat=True)),
                [category],
            )


class SchedulerTests(TestCase):
    @patch('news.apps.threading.Thread')
    def test_news_config_starts_separate_rss_and_shorts_pollers(self, thread_mock):
        thread_instance = MagicMock()
        thread_mock.return_value = thread_instance

        with patch.dict('news.apps.os.environ', {'RUN_MAIN': 'true'}, clear=False):
            with patch('news.apps.sys.argv', ['manage.py', 'runserver']):
                NewsConfig('news', import_module('news')).ready()

        self.assertEqual(thread_mock.call_count, 2)
        self.assertEqual(thread_instance.start.call_count, 2)
        self.assertEqual(thread_mock.call_args_list[0].kwargs['name'], 'rss-feed-scheduler')
        self.assertEqual(thread_mock.call_args_list[1].kwargs['name'], 'youtube-shorts-scheduler')


class ShortsImportTests(TestCase):
    def test_youtube_channel_feed_is_imported_once_by_video_id(self):
        from .services import fetch_shorts_from_channel

        channel = YouTubeChannel.objects.create(channel_id='UC1234567890')
        feed = SimpleNamespace(entries=[{
            'yt_videoid': 'video123',
            'title': 'A Short',
            'summary': 'Description',
            'published': '2026-01-01T12:00:00Z',
        }])

        with patch('news.services.feedparser.parse', return_value=feed) as parse:
            self.assertEqual(fetch_shorts_from_channel(channel), 1)
            self.assertEqual(fetch_shorts_from_channel(channel), 0)

        self.assertEqual(Short.objects.count(), 1)
        self.assertEqual(Short.objects.get().channel, channel)
        self.assertIn('channel_id=UC1234567890', parse.call_args.args[0])

    def test_shorts_page_and_api_are_available(self):
        channel = YouTubeChannel.objects.create(channel_id='UCabcdefghij')
        Short.objects.create(channel=channel, video_id='video456', title='Another Short')

        self.assertEqual(self.client.get('/shorts/').status_code, 200)
        response = self.client.get('/api/shorts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['video_id'], 'video456')

    @patch('news.views.fetch_active_shorts', return_value=0)
    def test_shorts_views_refresh_from_youtube_before_rendering(self, fetch_mock):
        channel = YouTubeChannel.objects.create(channel_id='UCabcdefghij')
        Short.objects.create(channel=channel, video_id='video789', title='Fresh Short')

        page_response = self.client.get('/shorts/')
        api_response = self.client.get('/api/shorts/')

        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(api_response.status_code, 200)
        self.assertEqual(fetch_mock.call_count, 2)

    def test_shorts_are_returned_newest_first(self):
        channel = YouTubeChannel.objects.create(channel_id='UCabcdefghij')
        old_short = Short.objects.create(
            channel=channel,
            video_id='video-old',
            title='Old Short',
            published_at=timezone.make_aware(datetime(2026, 1, 1, 12, 0, 0)),
        )
        new_short = Short.objects.create(
            channel=channel,
            video_id='video-new',
            title='New Short',
            published_at=timezone.make_aware(datetime(2026, 1, 2, 12, 0, 0)),
        )

        response = self.client.get('/api/shorts/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['video_id'] for item in response.data['results'][:2]], ['video-new', 'video-old'])
        self.assertEqual(Short.objects.first(), new_short)


class ArticleModelTests(TestCase):
    def test_article_slug_and_default_status(self):
        article = Article.objects.create(
            title='Test Headline',
            source_url='https://example.com/test',
            category='technology',
        )
        self.assertEqual(article.slug, 'test-headline')
        self.assertEqual(article.status, 'draft')


class AdminActionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_rss_source_fetch_now_reports_errors_with_django_message_level(self):
        rss_source = RSSSource.objects.create(
            feed_name='Test Feed',
            feed_url='https://example.com/feed.xml',
            category='technology',
        )
        request = self.factory.get('/')
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))
        admin_instance = RSSSourceAdmin(RSSSource, admin.site)

        mock_feedparser = SimpleNamespace(parse=lambda url: (_ for _ in ()).throw(Exception('boom')))

        with patch.dict('sys.modules', {'feedparser': mock_feedparser}):
            with patch('requests.get', side_effect=Exception('boom')):
                admin_instance.fetch_now(request, RSSSource.objects.filter(pk=rss_source.pk))

        messages_list = list(self._messages(request))
        self.assertTrue(any(message.level == messages.ERROR for message in messages_list))

    def _messages(self, request):
        return list(messages.get_messages(request))


class AdminResourceLinkTests(TestCase):
    def test_admin_resource_links_open_in_a_new_tab_safely(self):
        article = Article.objects.create(
            title='Article with a source',
            source_url='https://example.com/article',
        )
        rss_source = RSSSource.objects.create(
            feed_name='Example feed',
            feed_url='https://example.com/feed.xml',
        )

        article_link = str(ArticleAdmin(Article, admin.site).article_url_link(article))
        feed_link = str(RSSSourceAdmin(RSSSource, admin.site).rss_url_link(rss_source))

        for link, url in ((article_link, article.source_url), (feed_link, rss_source.feed_url)):
            self.assertIn(f'href="{url}"', link)
            self.assertIn('target="_blank"', link)
            self.assertIn('rel="noopener noreferrer"', link)

    def test_published_badge_has_clean_status_text(self):
        article = Article.objects.create(
            title='Published article',
            source_url='https://example.com/published-article',
            is_published=True,
        )

        badge = str(ArticleAdmin(Article, admin.site).published_badge(article))

        self.assertIn('Published', badge)
        self.assertNotIn('âœ“', badge)

    def test_active_badge_has_clean_status_text(self):
        rss_source = RSSSource.objects.create(
            feed_name='Active feed',
            feed_url='https://example.com/active-feed.xml',
            is_active=True,
        )

        badge = str(RSSSourceAdmin(RSSSource, admin.site).active_badge(rss_source))

        self.assertIn('Active', badge)
        self.assertNotIn('â—', badge)

    def test_admin_delete_links_are_available_for_articles_and_shorts(self):
        channel = YouTubeChannel.objects.create(channel_id='UCdeleteadmin1')
        short = Short.objects.create(channel=channel, video_id='video-admin-delete', title='Short Admin Delete')
        article = Article.objects.create(
            title='Article Admin Delete',
            source_url='https://example.com/article-admin-delete',
        )

        article_link = str(ArticleAdmin(Article, admin.site).delete_link(article))
        short_link = str(ShortAdmin(Short, admin.site).delete_link(short))

        self.assertIn(reverse('admin:news_article_delete', args=[article.pk]), article_link)
        self.assertIn('Delete', article_link)
        self.assertIn(reverse('admin:news_short_delete', args=[short.pk]), short_link)
        self.assertIn('Delete', short_link)


class AuthAndApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='reader',
            email='reader@example.com',
            password='password123',
        )

    def test_register_login_me_and_logout_work_with_token_auth(self):
        register_response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'newreader',
                'email': 'newreader@example.com',
                'password': 'password123',
            },
            format='json',
        )
        self.assertEqual(register_response.status_code, 201)
        self.assertIn('token', register_response.data)

        login_response = self.client.post(
            '/api/auth/login/',
            {'username': 'reader', 'password': 'password123'},
            format='json',
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.data['token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        me_response = self.client.get('/api/auth/me/')
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data['username'], 'reader')

        logout_response = self.client.post('/api/auth/logout/')
        self.assertEqual(logout_response.status_code, 200)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_article_crud_like_and_comment_flow(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        create_response = self.client.post(
            '/api/crud/articles/',
            {
                'title': 'API Created Article',
                'source_url': 'https://example.com/api-created-article',
                'category': 'technology',
                'description': 'Created through the REST API.',
                'is_published': True,
                'status': 'published',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)
        slug = create_response.data['slug']

        like_response = self.client.post(f'/api/articles/{slug}/like/')
        self.assertEqual(like_response.status_code, 200)
        self.assertTrue(like_response.data['liked'])
        self.assertEqual(like_response.data['likes_count'], 1)

        unlike_response = self.client.post(f'/api/articles/{slug}/like/')
        self.assertEqual(unlike_response.status_code, 200)
        self.assertFalse(unlike_response.data['liked'])
        self.assertEqual(unlike_response.data['likes_count'], 0)

        comment_response = self.client.post(
            f'/api/articles/{slug}/comments/',
            {'body': 'Nice coverage.'},
            format='json',
        )
        self.assertEqual(comment_response.status_code, 201)
        comment_id = comment_response.data['id']
        self.assertEqual(comment_response.data['author'], 'reader')

        list_response = self.client.get(f'/api/articles/{slug}/comments/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data['results'][0]['body'], 'Nice coverage.')

        update_response = self.client.patch(
            f'/api/comments/{comment_id}/',
            {'body': 'Updated comment.'},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertTrue(update_response.data['is_edited'])

        delete_response = self.client.delete(f'/api/comments/{comment_id}/')
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(ArticleComment.objects.filter(pk=comment_id).exists())
