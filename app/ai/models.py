from __future__ import annotations

from django.conf import settings
from django.db import models


class RecipeGenerationJobStatus(models.TextChoices):
    QUEUED = "queued", "Eilėje"
    RUNNING = "running", "Vykdoma"
    SUCCEEDED = "succeeded", "Pavyko"
    FAILED = "failed", "Nepavyko"


class RecipeGenerationJob(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipe_generation_jobs",
    )

    status = models.CharField(
        max_length=20,
        choices=RecipeGenerationJobStatus.choices,
        default=RecipeGenerationJobStatus.QUEUED,
    )

    inputs = models.JSONField(default=dict)
    selected_ingredient_ids = models.JSONField(default=list)

    result_recipe = models.ForeignKey(
        "recipes.Recipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generation_jobs",
    )

    error = models.TextField(blank=True)
    token_usage = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"RecipeGenerationJob#{self.pk} ({self.status})"
