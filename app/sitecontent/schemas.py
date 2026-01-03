"""Ninja schemos globaliam svetainės turiniui."""

from typing import Optional

from ninja import Schema


class HeaderDropdownSchema(Schema):
    id: int
    title: str
    link: Optional[str] = None
    icon_svg: Optional[str] = None
    image: Optional[str] = None
    order: int


class HeaderMenuSchema(Schema):
    id: int
    title: str
    link: Optional[str] = None
    is_dropdown: bool
    icon_svg: Optional[str] = None
    image: Optional[str] = None
    order: int
    dropdown_items: list[HeaderDropdownSchema]


class SiteHeaderSchema(Schema):
    id: int
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    description_html: Optional[str] = None
    logo: Optional[str] = None
    menu_items: list[HeaderMenuSchema]


class FooterColumnSchema(Schema):
    id: int
    title: str
    order: int
    column_type: str
    link_title: Optional[str] = None
    link: Optional[str] = None
    html_block: Optional[str] = None


class FooterSchema(Schema):
    id: int
    hero_text_html: Optional[str] = None
    text_after_footer: Optional[str] = None
    hero_image: Optional[str] = None
    columns: list[FooterColumnSchema]


class HeroBlockSchema(Schema):
    id: int
    title: str
    subtitle: Optional[str] = None
    hero_text_html: Optional[str] = None
    image: Optional[str] = None
