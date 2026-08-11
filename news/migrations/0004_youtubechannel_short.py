from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0003_remove_entertainment_and_food')]

    operations = [
        migrations.CreateModel(
            name='YouTubeChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel_id', models.CharField(help_text='YouTube Channel ID (starts with UC)', max_length=64, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('last_fetched', models.DateTimeField(blank=True, null=True)),
                ('shorts_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-is_active', '-updated_at']},
        ),
        migrations.CreateModel(
            name='Short',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('video_id', models.CharField(max_length=32, unique=True)),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('thumbnail_url', models.URLField(blank=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('channel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shorts', to='news.youtubechannel')),
            ],
            options={'ordering': ['-published_at', '-created_at']},
        ),
    ]
