"""Centrinis Ninja API objektas ir bendri hook'ai."""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI

from accounts.api import router as accounts_router
from recipes.api import router as recipes_router
from sitecontent.api import router as sitecontent_router

docs_enabled = getattr(settings, "NINJA_ENABLE_DOCS", settings.DEBUG)
docs_decorator = (
    staff_member_required
    if getattr(settings, "NINJA_DOCS_REQUIRE_STAFF", not settings.DEBUG)
    else None
)

api = NinjaAPI(
    title="Recipe Platform API",
    version="0.1.0",
    description="Moderni receptų platformos API",
    openapi_url="/openapi.json" if docs_enabled else None,
    docs_url="/docs/" if docs_enabled else None,
    docs_decorator=docs_decorator,
)

api.add_router("/sitecontent", sitecontent_router)
api.add_router("/recipes", recipes_router)
api.add_router("/auth", accounts_router)
