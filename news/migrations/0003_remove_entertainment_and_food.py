from django.db import migrations, models


CATEGORY_CHOICES = [
    ('home', 'Home'),
    ('trending', 'Trending'),
    ('technology', 'Technology'),
    ('business', 'Business'),
    ('education', 'Education'),
    ('sports', 'Sports'),
    ('health', 'Health'),
    ('science', 'Science'),
]


def delete_removed_category_data(apps, schema_editor):
    Article = apps.get_model('news', 'Article')
    RSSSource = apps.get_model('news', 'RSSSource')
    Article.objects.filter(category__in=['entertainment', 'food']).delete()
    RSSSource.objects.filter(category__in=['entertainment', 'food']).delete()


class Migration(migrations.Migration):
    dependencies = [('news', '0002_rsssource')]

    operations = [
        migrations.RunPython(delete_removed_category_data, migrations.RunPython.noop),
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
