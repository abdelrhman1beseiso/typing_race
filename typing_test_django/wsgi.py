import os
import sys

project_path = "/home/abood1dev/typing_race"
if project_path not in sys.path:
    sys.path.insert(0, project_path)

os.environ["DJANGO_SETTINGS_MODULE"] = "typing_test_django.settings"

os.environ["DJANGO_SECRET_KEY"] = "jpp3fywqj=21^7-h0u+p^k^&_!o)x*$_jrcm&&jp$nx*fwj6vq"
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()