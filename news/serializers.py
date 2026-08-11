from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .models import Article, ArticleComment, ArticleLike, RSSSource, Short, YouTubeChannel

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs.get('username'),
            password=attrs.get('password'),
        )
        if not user:
            raise serializers.ValidationError('Invalid username or password.')
        attrs['user'] = user
        return attrs


class ArticleSerializer(serializers.ModelSerializer):
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    liked_by_user = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'image_url',
            'source_url',
            'published_at',
            'description',
            'category',
            'is_trending',
            'is_published',
            'status',
            'slug',
            'created_at',
            'updated_at',
            'likes_count',
            'comments_count',
            'liked_by_user',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'liked_by_user']

    def get_likes_count(self, obj):
        if hasattr(obj, 'likes_count'):
            return obj.likes_count
        return obj.likes.count()

    def get_comments_count(self, obj):
        if hasattr(obj, 'comments_count'):
            return obj.comments_count
        return obj.comments.count()

    def get_liked_by_user(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        if hasattr(obj, 'liked_by_user'):
            return bool(obj.liked_by_user)
        return ArticleLike.objects.filter(article=obj, user=user).exists()


class ShortSerializer(serializers.ModelSerializer):
    channel_id = serializers.CharField(source='channel.channel_id', read_only=True)
    watch_url = serializers.ReadOnlyField()

    class Meta:
        model = Short
        fields = ['id', 'channel', 'channel_id', 'video_id', 'title', 'description', 'thumbnail_url', 'published_at', 'watch_url']


class RSSSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RSSSource
        fields = [
            'id',
            'feed_name',
            'feed_url',
            'category',
            'is_active',
            'last_fetched',
            'articles_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['last_fetched', 'articles_count', 'created_at', 'updated_at']


class YouTubeChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = YouTubeChannel
        fields = [
            'id',
            'channel_id',
            'is_active',
            'last_fetched',
            'shorts_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['last_fetched', 'shorts_count', 'created_at', 'updated_at']


class ArticleCommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ArticleComment
        fields = ['id', 'article', 'author', 'body', 'is_edited', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'author', 'is_edited', 'created_at', 'updated_at']
