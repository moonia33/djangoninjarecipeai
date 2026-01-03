"""Top level URL maršrutai."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from recipe_platform.api import api

api_prefix = settings.NINJA_BASE_PATH or "api"
api_route = f"{api_prefix.strip('/')}/" if api_prefix else ""

urlpatterns = [
    path("admin/", admin.site.urls),
    path(api_route, api.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
