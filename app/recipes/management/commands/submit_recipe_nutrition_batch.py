from __future__ import annotations

import io
import json
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from openai import OpenAI

from recipes.models import RecipeNutritionJob, RecipeNutritionJobStatus
from recipes.nutrition_service import build_openai_chat_request


class Command(BaseCommand):
    help = "Sukuria OpenAI Batch iš queued RecipeNutritionJob įrašų (per naktį / 24h)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--completion-window",
            type=str,
            default="24h",
            help="OpenAI batch completion window (pvz. 24h).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nesiųsti į OpenAI, tik parodyti kiek job'ų pateiktų.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "OPENAI_API_KEY", ""):
            raise RuntimeError("OPENAI_API_KEY nenustatytas")

        limit: int = options["limit"]
        completion_window: str = options["completion_window"]
        dry_run: bool = options["dry_run"]

        # Paimam queued job'us, kurie dar nėra priskirti batch'ui.
        jobs = list(
            RecipeNutritionJob.objects.select_related("recipe")
            .filter(status=RecipeNutritionJobStatus.QUEUED)
            .order_by("created_at")[:limit]
        )

        if not jobs:
            self.stdout.write("Nėra queued job'ų")
            return

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"DRY-RUN: pateiktų job'ų: {len(jobs)}"))
            return

        # Build JSONL content: each line is a single request.
        lines: list[str] = []
        for job in jobs:
            body = build_openai_chat_request(recipe=job.recipe)
            lines.append(
                json.dumps(
                    {
                        "custom_id": f"nutrition_job:{job.id}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": body,
                    },
                    ensure_ascii=False,
                )
            )

        jsonl_bytes = ("\n".join(lines) + "\n").encode("utf-8")
        file_obj = io.BytesIO(jsonl_bytes)
        file_obj.name = "recipe_nutrition_batch.jsonl"  # required by SDK for multipart

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        uploaded = client.files.create(file=file_obj, purpose="batch")
        batch = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/chat/completions",
            completion_window=completion_window,
        )

        submitted_at = timezone.now()
        with transaction.atomic():
            RecipeNutritionJob.objects.filter(id__in=[j.id for j in jobs]).update(
                status=RecipeNutritionJobStatus.SUBMITTED,
                openai_batch_id=batch.id,
                openai_batch_submitted_at=submitted_at,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Batch sukurta: batch_id={batch.id} input_file_id={uploaded.id} jobs={len(jobs)}"
            )
        )
        self.stdout.write(
            f"Patarimas: pollink su: poetry run python manage.py poll_recipe_nutrition_batch --batch-id {batch.id}"
        )
