from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import UserConsents


@admin.register(UserConsents)
class UserConsentsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "newsletter_consent",
        "privacy_policy_consent",
        "terms_of_service_consent",
        "updated_at",
    )
    list_select_related = ("user",)
    search_fields = ("user__email", "user__username")
    list_filter = (
        "newsletter_consent",
        "privacy_policy_consent",
        "terms_of_service_consent",
    )


class UserConsentsInline(admin.StackedInline):
    model = UserConsents
    can_delete = False
    extra = 0
    verbose_name_plural = "Sutikimai"


User = get_user_model()

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [UserConsentsInline]
