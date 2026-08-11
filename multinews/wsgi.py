import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('django_settings_module', 'multinews.settings')
application = get_wsgi_application()
