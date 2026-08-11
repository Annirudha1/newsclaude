from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'crud/articles', views.ArticleViewSet, basename='crud-article')
router.register(r'crud/shorts', views.ShortViewSet, basename='crud-short')
router.register(r'crud/rss-sources', views.RSSSourceViewSet, basename='crud-rss-source')
router.register(r'crud/youtube-channels', views.YouTubeChannelViewSet, basename='crud-youtube-channel')

urlpatterns = [
    path('', views.index, name='index'),
    path('shorts/', views.shorts_page, name='shorts-page'),
    path('api/shorts/', views.ShortList.as_view(), name='short-list'),
    path('api/articles/', views.PublishedArticleList.as_view(), name='article-list'),
    path('api/articles/category/<str:category>/', views.PublishedArticleList.as_view(), name='article-category-list'),
    path('api/trending/', views.TrendingArticleList.as_view(), name='trending-list'),
    path('api/weather/', views.weather, name='weather'),
    path('api/markets/', views.markets, name='markets'),
    path('api/sports/live/', views.live_sports, name='live-sports'),
    path('api/latest/', views.LatestArticleList.as_view(), name='latest-list'),
    path('api/search/', views.SearchArticleList.as_view(), name='search-list'),
    path('api/filter/', views.filter_articles, name='filter-articles'),
    path('api/publish-filtered/', views.publish_filtered_articles, name='publish-filtered'),
    path('api/auth/register/', views.register, name='register'),
    path('api/auth/login/', views.login, name='login'),
    path('api/auth/logout/', views.logout, name='logout'),
    path('api/auth/me/', views.me, name='me'),
    path('api/articles/<slug:slug>/like/', views.toggle_article_like, name='article-like-toggle'),
    path('api/articles/<slug:slug>/comments/', views.ArticleCommentListCreateAPIView.as_view(), name='article-comments'),
    path('api/comments/<int:pk>/', views.ArticleCommentDetailAPIView.as_view(), name='comment-detail'),
    path('api/', include(router.urls)),
]
