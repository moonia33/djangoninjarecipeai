from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from recipes.models import Recipe, RecipeImageJob, RecipeImageJobStatus
from recipes.image_service import build_recipe_image_prompt


class Command(BaseCommand):
    help = "Sukuria hero paveikslo generavimo job'us receptams, kurie dar neturi paveikslo." 

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--include-non-generated",
            action="store_true",
            help="Įtraukti ir ne AI receptus (pagal nutylėjimą – tik is_generated=true).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti kiek būtų sukurta job'ų.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_non_generated: bool = options["include_non_generated"]
        dry_run: bool = options["dry_run"]

        active_jobs = RecipeImageJob.objects.filter(
            recipe_id=OuterRef("pk"),
            status__in=[RecipeImageJobStatus.QUEUED, RecipeImageJobStatus.RUNNING],
        )

        qs = (
            Recipe.objects.all()
            .annotate(has_active_job=Exists(active_jobs))
            .filter(image__isnull=True)
            .filter(has_active_job=False)
            .order_by("id")
        )

        if not include_non_generated:
            qs = qs.filter(is_generated=True)

        recipes = list(qs[:limit])

        created = 0
        for recipe in recipes:
            prompt = build_recipe_image_prompt(recipe=recipe)
            if dry_run:
                created += 1
                continue

            RecipeImageJob.objects.create(
                recipe_id=recipe.id,
                status=RecipeImageJobStatus.QUEUED,
                prompt=prompt,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Image job'ai: sukurta={created}, kandidatu={len(recipes)}"))
