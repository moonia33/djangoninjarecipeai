from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from recipes.models import Recipe, RecipeNutritionJob, RecipeNutritionJobStatus
from recipes.nutrition_service import compute_current_input_hash, generate_nutrition


class Command(BaseCommand):
    help = "Apdoroja queued RecipeNutritionJob įrašus ir užpildo Recipe.nutrition (OpenAI)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti ką apdorotų.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        dry_run: bool = options["dry_run"]

        processed = 0
        succeeded = 0
        failed = 0
        stale = 0

        for _ in range(limit):
            with transaction.atomic():
                job = (
                    RecipeNutritionJob.objects.select_for_update(skip_locked=True)
                    .select_related("recipe")
                    .filter(status=RecipeNutritionJobStatus.QUEUED)
                    .order_by("created_at")
                    .first()
                )

                if not job:
                    break

                recipe: Recipe = job.recipe
                current_hash = compute_current_input_hash(recipe)
                if current_hash != job.input_hash:
                    processed += 1
                    stale += 1
                    if not dry_run:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = "stale_job: recipe pasikeitė po enqueue"
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=recipe.pk).update(nutrition_dirty=True)
                    continue

                processed += 1
                if dry_run:
                    self.stdout.write(f"DRY-RUN: apdorotų job_id={job.id} recipe_id={recipe.id}")
                    continue

                job.status = RecipeNutritionJobStatus.RUNNING
                job.started_at = timezone.now()
                job.save(update_fields=["status", "started_at", "updated_at"])

            # OpenAI call outside the transaction to avoid holding DB locks.
            try:
                nutrition = generate_nutrition(recipe)
            except Exception as exc:
                with transaction.atomic():
                    job = RecipeNutritionJob.objects.select_for_update().get(pk=job.pk)
                    job.status = RecipeNutritionJobStatus.FAILED
                    job.error = str(exc)
                    job.finished_at = timezone.now()
                    job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                failed += 1
                continue

            with transaction.atomic():
                job = RecipeNutritionJob.objects.select_for_update().get(pk=job.pk)
                job.status = RecipeNutritionJobStatus.SUCCEEDED
                job.result = nutrition
                job.error = ""
                job.finished_at = timezone.now()
                job.save(update_fields=["status", "result", "error", "finished_at", "updated_at"])

                Recipe.objects.filter(pk=recipe.pk).update(
                    nutrition=nutrition,
                    nutrition_updated_at=timezone.now(),
                    nutrition_input_hash=job.input_hash,
                    nutrition_dirty=False,
                )

            succeeded += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Nutrition jobs: processed={processed} succeeded={succeeded} failed={failed} stale={stale}"
            )
        )
