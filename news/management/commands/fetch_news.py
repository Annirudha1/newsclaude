from django.core.management.base import BaseCommand, CommandError

from news.models import RSSSource
from news.services import fetch_active_sources, fetch_source


class Command(BaseCommand):
    help = 'Fetch active RSS feeds, skipping duplicate URLs and publishing new articles.'

    def add_arguments(self, parser):
        parser.add_argument('--source', type=int, help='Fetch one active RSS source by ID.')

    def handle(self, *args, **options):
        source_id = options.get('source')
        if source_id:
            try:
                source = RSSSource.objects.get(pk=source_id, is_active=True)
            except RSSSource.DoesNotExist as exc:
                raise CommandError(f'Active RSS source {source_id} does not exist.') from exc
            created = fetch_source(source)
            self.stdout.write(self.style.SUCCESS(f'{source.feed_name}: {created} new article(s)'))
            return

        created = fetch_active_sources()
        self.stdout.write(self.style.SUCCESS(f'Total fetched and published: {created} new article(s)'))
