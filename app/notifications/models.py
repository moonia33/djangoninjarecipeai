"""Modeliai el. laiškų šablonams valdyti."""

from django.db import models
from django.template import Context, Template


class EmailTemplate(models.Model):
    """Lankstus šablonas, kurį galima redaguoti per adminą."""

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Unikalus raktažodis šablono parinkimui kode.",
    )
    name = models.CharField(max_length=150, help_text="Pavadinimas admin'e.")
    subject = models.CharField(
        max_length=255, help_text="Tema su {{ kintamaisiais }}.")
    body_text = models.TextField(
        blank=True, help_text="Grynas tekstas (fallback).")
    body_html = models.TextField(
        blank=True, help_text="HTML versija su {{ kintamaisiais }}.")
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        verbose_name = "El. laiško šablonas"
        verbose_name_plural = "El. laiškų šablonai"

    def __str__(self) -> str:  # pragma: no cover - paprastas vaizdavimas
        return self.name or self.key

    def render_subject(self, context: dict | None = None) -> str:
        return self._render(self.subject, context)

    def render_text(self, context: dict | None = None) -> str:
        return self._render(self.body_text, context)

    def render_html(self, context: dict | None = None) -> str:
        return self._render(self.body_html, context)

    @staticmethod
    def _render(template_string: str, context: dict | None = None) -> str:
        if not template_string:
            return ""
        template = Template(template_string)
        return template.render(Context(context or {}))
