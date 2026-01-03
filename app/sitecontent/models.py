"""Modeliai globaliam svetainės turiniui."""

from django.db import models


class TimeStampedModel(models.Model):
    """Bazinė klasė su sukūrimo/atnaujinimo datomis."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteHeader(TimeStampedModel):
    """Pagrindinis puslapis: SEO ir logotipas."""

    meta_title = models.CharField(max_length=80, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    description_html = models.TextField(blank=True)
    logo = models.ImageField(
        upload_to="site/header/logo/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Header blokas"
        verbose_name_plural = "Header blokai"

    def __str__(self) -> str:  # pragma: no cover - reprezentacija adminui
        return self.meta_title or "Header"


class HeaderMenu(TimeStampedModel):
    """Pagrindinis meniu elementas."""

    header = models.ForeignKey(
        SiteHeader,
        related_name="menu_items",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True,
                            help_text="URL arba vidinis kelias.")
    is_dropdown = models.BooleanField(default=False)
    icon_svg = models.TextField(blank=True, help_text="Pilnas SVG fragmentas.")
    image = models.ImageField(
        upload_to="site/header/menu/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Header meniu"
        verbose_name_plural = "Header meniu"

    def __str__(self) -> str:  # pragma: no cover
        return self.title


class HeaderDropdownItem(TimeStampedModel):
    """Dropdown elementai konkrečiam meniu įrašui."""

    menu = models.ForeignKey(
        HeaderMenu,
        related_name="dropdown_items",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    icon_svg = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="site/header/dropdown/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["menu", "order"]
        verbose_name = "Dropdown nuoroda"
        verbose_name_plural = "Dropdown nuorodos"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.menu.title}: {self.title}"


class Footer(TimeStampedModel):
    """Footer struktūra su hero blokais ir tekstais."""

    hero_text_html = models.TextField(blank=True)
    text_after_footer = models.TextField(blank=True)
    hero_image = models.ImageField(
        upload_to="site/footer/hero/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Footer"
        verbose_name_plural = "Footer blokai"

    def __str__(self) -> str:  # pragma: no cover
        return f"Footer #{self.pk}" if self.pk else "Footer"


class FooterColumnType(models.TextChoices):
    LINK_LIST = ("linklist", "Nuorodų sąrašas")
    HTML = ("html_text", "HTML tekstas")


class FooterColumn(TimeStampedModel):
    """Atskiras footerio stulpelis."""

    footer = models.ForeignKey(
        Footer,
        related_name="columns",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    column_type = models.CharField(
        max_length=20, choices=FooterColumnType.choices)
    link_title = models.CharField(max_length=255, blank=True)
    link = models.CharField(max_length=255, blank=True)
    html_block = models.TextField(blank=True)

    class Meta:
        ordering = ["footer", "order"]
        verbose_name = "Footer stulpelis"
        verbose_name_plural = "Footer stulpeliai"

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.footer}: {self.title}"


class HeroBlock(TimeStampedModel):
    """Laisvai konfigūruojamas hero blokas."""

    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    hero_text_html = models.TextField(blank=True)
    image = models.ImageField(upload_to="site/hero/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Hero blokas"
        verbose_name_plural = "Hero blokai"

    def __str__(self) -> str:  # pragma: no cover
        return self.title
