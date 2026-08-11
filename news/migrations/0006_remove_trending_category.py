from django.db import migrations, models


CATEGORY_CHOICES = [
    ('home', 'Home'),
    ('technology', 'Technology'),
    ('business', 'Business'),
    ('education', 'Education'),
    ('sports', 'Sports'),
    ('health', 'Health'),
    ('science', 'Science'),
]


def move_trending_categories_to_home(apps, schema_editor):
    Article = apps.get_model('news', 'Article')
    RSSSource = apps.get_model('news', 'RSSSource')
    Article.objects.filter(category='trending').update(category='home')
    RSSSource.objects.filter(category='trending').update(category='home')


class Migration(migrations.Migration):
    dependencies = [('news', '0005_normalize_youtube_channel_ids')]

    operations = [
        migrations.RunPython(move_trending_categories_to_home, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='article',
            name='category',
            field=models.CharField(choices=CATEGORY_CHOICES, default='home', max_length=30),
        ),
        migrations.AlterField(
            model_name='rsssource',
            name='category',
            field=models.CharField(
                choices=CATEGORY_CHOICES,
                default='home',
                help_text='Category where articles from this feed will be imported',
                max_length=30,
            ),
        ),
    ]
