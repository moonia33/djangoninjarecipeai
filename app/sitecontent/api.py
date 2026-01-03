"""Ninja endpoint'ai globaliam svetainės turiniui."""

from django.db.models import Prefetch
from ninja import Router

from .models import (
    Footer,
    FooterColumn,
    HeaderDropdownItem,
    HeaderMenu,
    HeroBlock,
    SiteHeader,
)
from .schemas import (
    FooterSchema,
    HeroBlockSchema,
    SiteHeaderSchema,
    HeaderMenuSchema,
    HeaderDropdownSchema,
    FooterColumnSchema,
)

router = Router(tags=["Site content"])


def _abs_media_url(request, file_field) -> str | None:
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:  # file not saved
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return request.build_absolute_uri(url)


def _serialize_dropdown(request, dropdown: HeaderDropdownItem) -> HeaderDropdownSchema:
    return HeaderDropdownSchema(
        id=dropdown.id,
        title=dropdown.title,
        link=dropdown.link or None,
        icon_svg=dropdown.icon_svg or None,
        image=_abs_media_url(request, dropdown.image),
        order=dropdown.order,
    )


def _serialize_menu(request, menu: HeaderMenu) -> HeaderMenuSchema:
    return HeaderMenuSchema(
        id=menu.id,
        title=menu.title,
        link=menu.link or None,
        is_dropdown=menu.is_dropdown,
        icon_svg=menu.icon_svg or None,
        image=_abs_media_url(request, menu.image),
        order=menu.order,
        dropdown_items=[
            _serialize_dropdown(request, dropdown)
            for dropdown in menu.dropdown_items.all()
        ],
    )


def _serialize_header(request, header: SiteHeader) -> SiteHeaderSchema:
    return SiteHeaderSchema(
        id=header.id,
        meta_title=header.meta_title or None,
        meta_description=header.meta_description or None,
        meta_keywords=header.meta_keywords or None,
        description_html=header.description_html or None,
        logo=_abs_media_url(request, header.logo),
        menu_items=[_serialize_menu(request, menu)
                    for menu in header.menu_items.all()],
    )


def _serialize_footer(request, footer: Footer) -> FooterSchema:
    return FooterSchema(
        id=footer.id,
        hero_text_html=footer.hero_text_html or None,
        text_after_footer=footer.text_after_footer or None,
        hero_image=_abs_media_url(request, footer.hero_image),
        columns=[
            FooterColumnSchema(
                id=column.id,
                title=column.title,
                order=column.order,
                column_type=column.column_type,
                link_title=column.link_title or None,
                link=column.link or None,
                html_block=column.html_block or None,
            )
            for column in footer.columns.all()
        ],
    )


def _serialize_hero(request, hero: HeroBlock) -> HeroBlockSchema:
    return HeroBlockSchema(
        id=hero.id,
        title=hero.title,
        subtitle=hero.subtitle or None,
        hero_text_html=hero.hero_text_html or None,
        image=_abs_media_url(request, hero.image),
    )


@router.get("/header", response=SiteHeaderSchema | None)
def get_header(request):
    dropdown_prefetch = Prefetch(
        "dropdown_items", queryset=HeaderDropdownItem.objects.order_by("order")
    )
    menu_prefetch = Prefetch(
        "menu_items",
        queryset=HeaderMenu.objects.order_by(
            "order").prefetch_related(dropdown_prefetch),
    )
    header = (
        SiteHeader.objects.filter(is_active=True)
        .prefetch_related(menu_prefetch)
        .order_by("-updated_at")
        .first()
    )
    if not header:
        return None
    return _serialize_header(request, header)


@router.get("/footer", response=FooterSchema | None)
def get_footer(request):
    footer = (
        Footer.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "columns", queryset=FooterColumn.objects.order_by("order")
            )
        )
        .order_by("-updated_at")
        .first()
    )
    if not footer:
        return None
    return _serialize_footer(request, footer)


@router.get("/heroes", response=list[HeroBlockSchema])
def list_heroes(request):
    heroes = HeroBlock.objects.filter(is_active=True).order_by("title")
    return [_serialize_hero(request, hero) for hero in heroes]
