"""Admino konfigūracija el. laiškų šablonams."""

from django.contrib import admin

from . import models


@admin.register(models.EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key", "subject", "body_text", "body_html")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("is_active", "name", "key", "description")}),
        ("Turinys", {"fields": ("subject", "body_text", "body_html")}),
        ("Meta", {"fields": ("created_at", "updated_at")}),
    )
