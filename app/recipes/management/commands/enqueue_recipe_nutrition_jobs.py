from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from recipes.models import Recipe, RecipeIngredient, RecipeNutritionJob, RecipeNutritionJobStatus


class Command(BaseCommand):
    help = "Sukuria nutrition job'us receptams, kuriems reikia perskaičiuoti maistinę vertę."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Įtraukti ir nepublikuotus receptus (published_at IS NULL).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignoruoti nutrition_dirty ir bandyti sukurti job'us visiems (vis tiek praleidžia jei yra active job).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti kiek būtų sukurta job'ų.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_drafts: bool = options["include_drafts"]
        force: bool = options["force"]
        dry_run: bool = options["dry_run"]

        active_jobs = RecipeNutritionJob.objects.filter(
            recipe_id=OuterRef("pk"),
            status__in=[RecipeNutritionJobStatus.QUEUED, RecipeNutritionJobStatus.RUNNING],
        )

        qs = Recipe.objects.all().annotate(has_active_job=Exists(active_jobs))
        if not include_drafts:
            qs = qs.filter(published_at__isnull=False)
        if not force:
            qs = qs.filter(Q(nutrition__isnull=True) | Q(nutrition_dirty=True))
        qs = qs.filter(has_active_job=False).order_by("id")

        recipes = list(qs[:limit])

        created = 0
        skipped_no_ingredients = 0

        for recipe in recipes:
            ingredient_rows = list(
                RecipeIngredient.objects.filter(recipe_id=recipe.id)
                .values_list("ingredient_id", "group_id", "unit_id", "amount", "note")
                .order_by("ingredient_id", "group_id", "unit_id", "amount", "id")
            )
            if not ingredient_rows:
                skipped_no_ingredients += 1
                continue

            input_hash = RecipeNutritionJob.compute_input_hash(
                servings=recipe.servings,
                ingredient_rows=ingredient_rows,
            )

            if dry_run:
                created += 1
                continue

            RecipeNutritionJob.objects.create(
                recipe_id=recipe.id,
                status=RecipeNutritionJobStatus.QUEUED,
                input_hash=input_hash,
            )
            Recipe.objects.filter(pk=recipe.id).update(nutrition_last_enqueued_at=timezone.now())
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Nutrition job'ai: sukurta={created}, praleista_be_ingredientu={skipped_no_ingredients}, kandidatu={len(recipes)}"
            )
        )
