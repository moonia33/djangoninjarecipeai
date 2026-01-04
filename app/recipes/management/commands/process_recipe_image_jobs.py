from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from recipes.image_service import build_recipe_image_prompt, generate_recipe_image
from recipes.models import RecipeImageJob, RecipeImageJobStatus


class Command(BaseCommand):
    help = "Apdoroja queued RecipeImageJob įrašus ir prisega sugeneruotą paveikslą prie Recipe.image." 

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        limit: int = options["limit"]

        processed = 0
        succeeded = 0
        failed = 0

        while processed < limit:
            with transaction.atomic():
                job = (
                    RecipeImageJob.objects.select_for_update(skip_locked=True)
                    .select_related("recipe")
                    .filter(status=RecipeImageJobStatus.QUEUED)
                    .order_by("created_at")
                    .first()
                )

                if not job:
                    break

                # Idempotency / fast path
                if getattr(job.recipe, "image", None):
                    job.status = RecipeImageJobStatus.SUCCEEDED
                    job.error = ""
                    job.finished_at = timezone.now()
                    job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                    processed += 1
                    succeeded += 1
                    continue

                job.status = RecipeImageJobStatus.RUNNING
                job.started_at = timezone.now()
                if not (job.prompt or "").strip():
                    job.prompt = build_recipe_image_prompt(recipe=job.recipe)
                job.error = ""
                job.save(update_fields=["status", "started_at", "prompt", "error", "updated_at"])

            # Do the expensive part outside the lock.
            try:
                gen = generate_recipe_image(prompt=job.prompt)
                filename_slug = getattr(job.recipe, "slug", "recipe") or "recipe"
                filename = f"{filename_slug}-ai.png"

                content = ContentFile(gen.content)
                content.name = filename

                # Save image to recipe
                with transaction.atomic():
                    locked = RecipeImageJob.objects.select_for_update().select_related("recipe").get(pk=job.pk)
                    if locked.status != RecipeImageJobStatus.RUNNING:
                        # Someone else handled it.
                        processed += 1
                        continue

                    if getattr(locked.recipe, "image", None):
                        locked.status = RecipeImageJobStatus.SUCCEEDED
                        locked.error = ""
                        locked.finished_at = timezone.now()
                        locked.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        processed += 1
                        succeeded += 1
                        continue

                    locked.recipe.image.save(content.name, content, save=True)

                    locked.status = RecipeImageJobStatus.SUCCEEDED
                    locked.error = ""
                    locked.finished_at = timezone.now()
                    locked.save(update_fields=["status", "error", "finished_at", "updated_at"])

                processed += 1
                succeeded += 1
            except Exception as exc:
                with transaction.atomic():
                    locked = RecipeImageJob.objects.select_for_update().get(pk=job.pk)
                    locked.status = RecipeImageJobStatus.FAILED
                    locked.error = str(exc)[:4000]
                    locked.finished_at = timezone.now()
                    locked.save(update_fields=["status", "error", "finished_at", "updated_at"])

                processed += 1
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Image worker: processed={processed} succeeded={succeeded} failed={failed}"
            )
        )
