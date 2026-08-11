from django.core.management.base import BaseCommand, CommandError

from news.models import YouTubeChannel
from news.services import fetch_active_shorts, fetch_shorts_from_channel


class Command(BaseCommand):
    help = 'Generate YouTube feeds from saved Channel IDs and import new Shorts.'

    def add_arguments(self, parser):
        parser.add_argument('--channel', type=int, help='Fetch one active channel by database ID.')

    def handle(self, *args, **options):
        channel_id = options.get('channel')
        if channel_id:
            try:
                channel = YouTubeChannel.objects.get(pk=channel_id, is_active=True)
            except YouTubeChannel.DoesNotExist as exc:
                raise CommandError(f'Active YouTube channel {channel_id} does not exist.') from exc
            created = fetch_shorts_from_channel(channel)
            self.stdout.write(self.style.SUCCESS(f'{channel.channel_id}: {created} new Short(s) imported.'))
            return

        created = fetch_active_shorts()
        self.stdout.write(self.style.SUCCESS(f'Total Shorts imported: {created}'))
