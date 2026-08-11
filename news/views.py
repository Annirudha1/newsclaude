import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
import requests
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Article, ArticleComment, ArticleLike, RSSSource, Short, YouTubeChannel
from .serializers import (
    ArticleCommentSerializer,
    ArticleSerializer,
    LoginSerializer,
    RegisterSerializer,
    RSSSourceSerializer,
    ShortSerializer,
    UserSerializer,
    YouTubeChannelSerializer,
)
from .services import fetch_active_shorts


logger = logging.getLogger(__name__)
class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (request.user.is_staff or getattr(obj, 'user_id', None) == request.user.id)


class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all().order_by('-published_at', '-created_at')
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'category', 'slug']
    ordering_fields = ['published_at', 'created_at', 'updated_at']
    ordering = ['-published_at', '-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_published=True)
        queryset = queryset.annotate(
            likes_count=Count('likes', distinct=True),
            comments_count=Count('comments', distinct=True),
        )
        return queryset


class ShortViewSet(viewsets.ModelViewSet):
    queryset = Short.objects.select_related('channel').all().order_by('-published_at', '-created_at')
    serializer_class = ShortSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'video_id', 'channel__channel_id']
    ordering_fields = ['published_at', 'created_at']
    ordering = ['-published_at', '-created_at']


class RSSSourceViewSet(viewsets.ModelViewSet):
    queryset = RSSSource.objects.all().order_by('-is_active', '-updated_at')
    serializer_class = RSSSourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['feed_name', 'feed_url', 'category']
    ordering_fields = ['updated_at', 'created_at', 'articles_count']


class YouTubeChannelViewSet(viewsets.ModelViewSet):
    queryset = YouTubeChannel.objects.all().order_by('-is_active', '-updated_at')
    serializer_class = YouTubeChannelSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['channel_id']
    ordering_fields = ['updated_at', 'created_at', 'shorts_count']


class ArticleCommentListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ArticleCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return ArticleComment.objects.filter(article__slug=self.kwargs['slug']).select_related('article', 'user')

    def perform_create(self, serializer):
        article = get_object_or_404(Article, slug=self.kwargs['slug'])
        serializer.save(article=article, user=self.request.user)


class ArticleCommentDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ArticleComment.objects.select_related('article', 'user')
    serializer_class = ArticleCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrAdmin]

    def perform_update(self, serializer):
        serializer.save(is_edited=True)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def toggle_article_like(request, slug):
    article = get_object_or_404(Article, slug=slug)
    like, created = ArticleLike.objects.get_or_create(article=article, user=request.user)
    if created:
        liked = True
    else:
        like.delete()
        liked = False

    return Response({
        'slug': article.slug,
        'liked': liked,
        'likes_count': article.likes.count(),
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'user': UserSerializer(user).data})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Logged out successfully.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


def _refresh_shorts_from_youtube():
    """Keep Shorts in sync with configured YouTube channels before serving them."""
    try:
        return fetch_active_shorts()
    except Exception:
        logger.exception('Failed to refresh YouTube Shorts.')
        return 0


def index(request):
    return render(request, 'index.html')


def shorts_page(request):
    _refresh_shorts_from_youtube()
    shorts = Short.objects.select_related('channel').order_by('-published_at', '-created_at')
    return render(request, 'shorts.html', {'shorts': shorts})


class ShortList(generics.ListAPIView):
    serializer_class = ShortSerializer

    def get_queryset(self):
        _refresh_shorts_from_youtube()
        return Short.objects.select_related('channel').order_by('-published_at', '-created_at')[:30]


class PublishedArticleList(generics.ListAPIView):
    serializer_class = ArticleSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description']

    def get_queryset(self):
        queryset = Article.objects.filter(is_published=True).order_by('-published_at', '-created_at')
        category = self.kwargs.get('category')
        if category and category != 'home':
            queryset = queryset.filter(category=category)
        return queryset


class TrendingArticleList(generics.ListAPIView):
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.filter(is_published=True, is_trending=True).order_by('-published_at', '-created_at')[:8]


@api_view(['GET'])
def weather(request):
    """Return a cached Delhi weather summary without exposing the API key."""
    cache_key = 'dashboard:weather:delhi'
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    if not settings.OPENWEATHER_API_KEY:
        return Response({'detail': 'Weather service is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        response = requests.get(
            'https://api.openweathermap.org/data/2.5/weather',
            params={'q': 'Delhi', 'appid': settings.OPENWEATHER_API_KEY, 'units': 'metric'},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        result = {
            'city': data.get('name', 'Delhi'),
            'temperature': round(data['main']['temp']),
            'condition': (data.get('weather') or [{}])[0].get('main', 'Unknown'),
            'humidity': data['main'].get('humidity'),
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return Response({'detail': 'Weather data is temporarily unavailable.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    cache.set(cache_key, result, 600)
    return Response(result)


@api_view(["GET"])
def markets(request):
    cache_key = "dashboard:markets:india"

    cached = cache.get(cache_key)
    if cached:
        return Response(cached)

    if not settings.TWELVE_DATA_API_KEY:
        return Response(
            {"detail": "Market service is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    results = []

    MARKETS = [
        ("Gold", "XAU/USD"),
        ("Silver", "XAG/USD"),
        ("Nifty 50", "NIFTY:NSE"),
        ("Sensex", "SENSEX:BSE"),
    ]

    for label, symbol in MARKETS:
        try:
            response = requests.get(
                "https://api.twelvedata.com/quote",
                params={
                    "symbol": symbol,
                    "apikey": settings.TWELVE_DATA_API_KEY,
                },
                timeout=10,
            )

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "error":
                print(label, data)
                continue

            results.append(
                {
                    "name": label,
                    "price": data.get("close") or data.get("price"),
                    "change": f"{float(data.get('percent_change', 0)):+.2f}%",
                }
            )

        except Exception as e:
            print(label, e)
            continue

    if not results:
        return Response(
            {"detail": "Market data is temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    result = {"indices": results}
    cache.set(cache_key, result, 900)

    return Response(result)


@api_view(["GET"])
def live_sports(request):
    """Return the latest published sports coverage for the dashboard."""
    articles = (
        Article.objects
        .filter(is_published=True, category="sports")
        .order_by("-published_at", "-created_at")[:8]
    )
    return Response({
        "results": ArticleSerializer(articles, many=True).data,
        "count": len(articles),
    })


class LatestArticleList(generics.ListAPIView):
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.filter(is_published=True).order_by('-published_at', '-created_at')[:12]


class SearchArticleList(generics.ListAPIView):
    serializer_class = ArticleSerializer

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        return (
            Article.objects
            .filter(is_published=True)
            .filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(category__icontains=query)
            )
            .order_by('-published_at', '-created_at')[:20]
        )


@api_view(['GET'])
def filter_articles(request):
    """Filter articles by category and status"""
    category = request.query_params.get('category', '')
    article_status = request.query_params.get('status', '')
    
    queryset = Article.objects.all().order_by('-published_at', '-created_at')
    
    if category:
        queryset = queryset.filter(category=category)
    if article_status:
        queryset = queryset.filter(status=article_status)
    
    serializer = ArticleSerializer(queryset, many=True)
    return Response({
        'results': serializer.data,
        'count': queryset.count()
    })


@api_view(['POST'])
def publish_filtered_articles(request):
    """Publish all articles matching filter criteria"""
    category = request.query_params.get('category', '')
    article_status = request.query_params.get('status', '')
    
    queryset = Article.objects.all()
    
    if category:
        queryset = queryset.filter(category=category)
    if article_status:
        queryset = queryset.filter(status=article_status)
    
    updated_count = queryset.update(is_published=True, status='published')
    
    return Response({
        'success': True,
        'message': f'{updated_count} article(s) published successfully.',
        'updated_count': updated_count
    })
