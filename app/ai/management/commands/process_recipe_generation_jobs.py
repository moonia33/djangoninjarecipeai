from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ai.models import RecipeGenerationJob, RecipeGenerationJobStatus
from ai.services import generate_recipe_from_payload
from recipes.models import Difficulty, Recipe, RecipeStep

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Apdoroja RecipeGenerationJob: kviečia OpenAI ir sukuria Recipe + Steps (MVP)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5)

    def handle(self, *args, **options):
        limit: int = options["limit"]
        processed = 0
        failed = 0

        jobs = list(
            RecipeGenerationJob.objects.filter(status=RecipeGenerationJobStatus.QUEUED)
            .select_related("user")
            .order_by("created_at")[:limit]
        )

        for job in jobs:
            processed += 1
            try:
                self._process_one(job)
            except Exception:
                failed += 1
                logger.exception("Nepavyko apdoroti RecipeGenerationJob (id=%s)", job.id)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. processed={processed} failed={failed}"
            )
        )

    def _process_one(self, job: RecipeGenerationJob) -> None:
        # Perjungiam į RUNNING kuo anksčiau, kad nedubliuotųsi workeriai.
        updated = RecipeGenerationJob.objects.filter(
            id=job.id, status=RecipeGenerationJobStatus.QUEUED
        ).update(status=RecipeGenerationJobStatus.RUNNING, started_at=timezone.now(), error="")
        if updated == 0:
            return

        job.refresh_from_db()

        try:
            generated, token_usage = generate_recipe_from_payload(payload=job.inputs)
        except Exception as exc:
            RecipeGenerationJob.objects.filter(id=job.id).update(
                status=RecipeGenerationJobStatus.FAILED,
                finished_at=timezone.now(),
                error=str(exc),
            )
            raise

        # MVP: ingredientus įrašom į Recipe.description kaip Markdown, žingsnius – į RecipeStep.
        ingredients_md = "\n".join(f"- {line}" for line in generated.ingredients if str(line).strip())
        full_description = generated.description.strip()
        if ingredients_md:
            full_description = f"{full_description}\n\n## Ingredientai\n{ingredients_md}\n"
        if generated.note:
            full_description = f"{full_description}\n\n## Pastaba\n{generated.note.strip()}\n"

        difficulty_value = generated.difficulty
        if difficulty_value not in {Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD}:
            difficulty_value = Difficulty.MEDIUM

        with transaction.atomic():
            recipe = Recipe.objects.create(
                title=generated.title,
                description=full_description,
                note="",
                is_generated=True,
                preparation_time=int(generated.preparation_time),
                cooking_time=int(generated.cooking_time),
                servings=int(generated.servings),
                difficulty=difficulty_value,
            )

            steps = sorted(generated.steps, key=lambda s: s.order)
            for step in steps:
                RecipeStep.objects.create(
                    recipe=recipe,
                    order=int(step.order),
                    title=(step.title or "").strip(),
                    description=step.description.strip(),
                    duration=int(step.duration) if step.duration is not None else None,
                )

            RecipeGenerationJob.objects.filter(id=job.id).update(
                status=RecipeGenerationJobStatus.SUCCEEDED,
                finished_at=timezone.now(),
                result_recipe=recipe,
                token_usage=token_usage,
            )
