import logging
import os
import sys
import threading

from django.apps import AppConfig
from django.conf import settings


logger = logging.getLogger(__name__)


class NewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news'

    def ready(self):
        """Fetch active feeds on startup and then on separate polling intervals."""
        if any(command in sys.argv for command in ('test', 'migrate', 'makemigrations', 'collectstatic', 'shell')):
            return
        # The development auto-reloader starts Django twice. Only schedule in its child.
        if (
            settings.DEBUG
            and os.environ.get('RUN_MAIN') != 'true'
            and '--noreload' not in sys.argv
        ):
            return

        rss_interval = getattr(settings, 'RSS_FETCH_INTERVAL_SECONDS', 600)
        shorts_interval = getattr(settings, 'SHORTS_FETCH_INTERVAL_SECONDS', 60)

        threading.Thread(
            target=self._run_feed_scheduler,
            args=(rss_interval,),
            name='rss-feed-scheduler',
            daemon=True,
        ).start()

        threading.Thread(
            target=self._run_shorts_scheduler,
            args=(shorts_interval,),
            name='youtube-shorts-scheduler',
            daemon=True,
        ).start()

    @staticmethod
    def _run_feed_scheduler(interval):
        from .services import fetch_active_sources

        while True:
            try:
                fetch_active_sources()
            except Exception:
                logger.exception('Scheduled RSS fetch failed.')
            threading.Event().wait(interval)

    @staticmethod
    def _run_shorts_scheduler(interval):
        from .services import fetch_active_shorts

        while True:
            try:
                fetch_active_shorts()
            except Exception:
                logger.exception('Scheduled YouTube Shorts fetch failed.')
            threading.Event().wait(interval)
