from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from openai import OpenAI

from recipes.models import Recipe, RecipeNutritionJob, RecipeNutritionJobStatus
from recipes.nutrition_service import parse_openai_chat_content_to_nutrition


def _iter_jsonl_lines(text: str):
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        yield json.loads(raw)


class Command(BaseCommand):
    help = "Patikrina OpenAI Batch būseną ir suimportuoja rezultatus į RecipeNutritionJob/Recipe." 

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-id",
            type=str,
            default=None,
            help="Jei nurodyta – pollinama tik ši batch. Jei nenurodyta – pollinamos visos SUBMITTED batch'ų grupės.",
        )
        parser.add_argument(
            "--max-batches",
            type=int,
            default=10,
            help="Kiek skirtingų batch'ų apdoroti per vieną paleidimą.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "OPENAI_API_KEY", ""):
            raise RuntimeError("OPENAI_API_KEY nenustatytas")

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        batch_id: str | None = options["batch_id"]
        max_batches: int = options["max_batches"]

        if batch_id:
            batch_ids = [batch_id]
        else:
            batch_ids = list(
                RecipeNutritionJob.objects.filter(
                    status=RecipeNutritionJobStatus.SUBMITTED,
                )
                .exclude(openai_batch_id__isnull=True)
                .exclude(openai_batch_id="")
                .values_list("openai_batch_id", flat=True)
                .distinct()[:max_batches]
            )

        if not batch_ids:
            self.stdout.write("Nėra SUBMITTED batch'ų")
            return

        processed_jobs = 0
        succeeded = 0
        failed = 0

        for bid in batch_ids:
            batch = client.batches.retrieve(bid)
            status = getattr(batch, "status", None) or ""
            self.stdout.write(f"batch_id={bid} status={status}")

            if status in {"validating", "in_progress", "finalizing", "queued"}:
                continue

            if status in {"failed", "expired", "canceled"}:
                # Mark all jobs in this batch as failed (unless already succeeded).
                with transaction.atomic():
                    qs = RecipeNutritionJob.objects.select_for_update().filter(
                        openai_batch_id=bid,
                        status=RecipeNutritionJobStatus.SUBMITTED,
                    )
                    for job in qs:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = f"batch_{status}"
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=job.recipe_id).update(nutrition_dirty=True)
                        processed_jobs += 1
                        failed += 1
                continue

            if status != "completed":
                continue

            output_file_id = getattr(batch, "output_file_id", None)
            if not output_file_id:
                self.stdout.write(f"batch_id={bid} completed, bet nėra output_file_id")
                continue

            content = client.files.content(output_file_id)
            # SDK grąžina skirtingus response tipus priklausomai nuo versijos.
            if hasattr(content, "text") and content.text is not None:
                text = content.text
            else:
                raw = content.read() if hasattr(content, "read") else bytes(content)
                text = raw.decode("utf-8")

            # Output format: JSONL. Each line has custom_id and response/error.
            for line in _iter_jsonl_lines(text):
                custom_id = line.get("custom_id")
                if not custom_id or not custom_id.startswith("nutrition_job:"):
                    continue

                try:
                    job_id = int(custom_id.split(":", 1)[1])
                except Exception:
                    continue

                with transaction.atomic():
                    job = (
                        RecipeNutritionJob.objects.select_for_update()
                        .select_related("recipe")
                        .get(pk=job_id)
                    )

                    # Idempotency: skip if already done.
                    if job.status in {RecipeNutritionJobStatus.SUCCEEDED, RecipeNutritionJobStatus.FAILED}:
                        continue

                    if job.openai_batch_id != bid:
                        continue

                    response = line.get("response")
                    err = line.get("error")

                    if err:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = json.dumps(err, ensure_ascii=False)[:4000]
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=job.recipe_id).update(nutrition_dirty=True)
                        processed_jobs += 1
                        failed += 1
                        continue

                    if not response:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = "missing_response"
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=job.recipe_id).update(nutrition_dirty=True)
                        processed_jobs += 1
                        failed += 1
                        continue

                    status_code = response.get("status_code")
                    body = response.get("body") or {}
                    if status_code != 200:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = json.dumps(body, ensure_ascii=False)[:4000]
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=job.recipe_id).update(nutrition_dirty=True)
                        processed_jobs += 1
                        failed += 1
                        continue

                    try:
                        content_text = body["choices"][0]["message"]["content"]
                        nutrition = parse_openai_chat_content_to_nutrition(
                            content=content_text,
                            servings=job.recipe.servings,
                        )
                    except Exception as exc:
                        job.status = RecipeNutritionJobStatus.FAILED
                        job.error = f"parse_error: {exc}"
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "error", "finished_at", "updated_at"])
                        Recipe.objects.filter(pk=job.recipe_id).update(nutrition_dirty=True)
                        processed_jobs += 1
                        failed += 1
                        continue

                    job.status = RecipeNutritionJobStatus.SUCCEEDED
                    job.result = nutrition
                    job.error = ""
                    job.finished_at = timezone.now()
                    job.save(update_fields=["status", "result", "error", "finished_at", "updated_at"])

                    Recipe.objects.filter(pk=job.recipe_id).update(
                        nutrition=nutrition,
                        nutrition_updated_at=timezone.now(),
                        nutrition_input_hash=job.input_hash,
                        nutrition_dirty=False,
                    )

                    processed_jobs += 1
                    succeeded += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Batch poll: processed_jobs={processed_jobs} succeeded={succeeded} failed={failed}"
            )
        )
