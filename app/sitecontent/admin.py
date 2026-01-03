"""Admino registracijos globaliam svetainės turiniui."""

from django.contrib import admin

from . import models


class HeaderMenuInline(admin.StackedInline):
    model = models.HeaderMenu
    extra = 0
    fields = (
        "order",
        "title",
        "link",
        "is_dropdown",
        "icon_svg",
        "image",
    )


@admin.register(models.SiteHeader)
class SiteHeaderAdmin(admin.ModelAdmin):
    list_display = ("meta_title", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("meta_title", "meta_description")
    inlines = [HeaderMenuInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("is_active",)}),
        ("SEO", {"fields": ("meta_title", "meta_description", "meta_keywords")}),
        ("Turinys", {"fields": ("description_html", "logo")}),
        ("Datos", {"fields": ("created_at", "updated_at")}),
    )


class HeaderDropdownInline(admin.StackedInline):
    model = models.HeaderDropdownItem
    extra = 0
    fields = ("order", "title", "link", "icon_svg", "image")


@admin.register(models.HeaderMenu)
class HeaderMenuAdmin(admin.ModelAdmin):
    list_display = ("title", "header", "is_dropdown", "order")
    list_filter = ("is_dropdown", "header")
    search_fields = ("title", "link")
    ordering = ("header", "order")
    inlines = [HeaderDropdownInline]


class FooterColumnInline(admin.StackedInline):
    model = models.FooterColumn
    extra = 0
    fields = ("order", "title", "column_type",
              "link_title", "link", "html_block")


@admin.register(models.Footer)
class FooterAdmin(admin.ModelAdmin):
    list_display = ("id", "is_active", "updated_at")
    list_filter = ("is_active",)
    inlines = [FooterColumnInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("is_active",)}),
        ("Turinys", {"fields": ("hero_text_html",
                                "text_after_footer", "hero_image")}),
        ("Datos", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(models.FooterColumn)
class FooterColumnAdmin(admin.ModelAdmin):
    list_display = ("title", "footer", "column_type", "order")
    list_filter = ("column_type", "footer")
    ordering = ("footer", "order")


@admin.register(models.HeroBlock)
class HeroBlockAdmin(admin.ModelAdmin):
    list_display = ("title", "subtitle", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle")
    readonly_fields = ("created_at", "updated_at")
