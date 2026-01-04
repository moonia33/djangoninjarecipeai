from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ai.models import RecipeGenerationJob, RecipeGenerationJobStatus
from ai.services import generate_recipe_from_payload
from recipes.models import (
    Difficulty,
    Ingredient,
    IngredientCategory,
    MeasurementUnit,
    MeasurementUnitType,
    Recipe,
    RecipeIngredient,
    RecipeStep,
)

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

        full_description = generated.description.strip()

        difficulty_value = generated.difficulty
        if difficulty_value not in {Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD}:
            difficulty_value = Difficulty.MEDIUM

        with transaction.atomic():
            recipe = Recipe.objects.create(
                title=generated.title,
                description=full_description,
                note=(generated.note or "").strip(),
                is_generated=True,
                preparation_time=int(generated.preparation_time),
                cooking_time=int(generated.cooking_time),
                servings=int(generated.servings),
                difficulty=difficulty_value,
            )

            default_category = self._get_or_create_default_ingredient_category()
            self._persist_ingredients(recipe=recipe, items=generated.ingredients, default_category=default_category)

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

    def _get_or_create_default_ingredient_category(self) -> IngredientCategory:
        existing = IngredientCategory.objects.order_by("id").first()
        if existing:
            return existing
        return IngredientCategory.objects.create(name="Kita")

    def _guess_unit_type(self, short_name: str) -> str:
        s = (short_name or "").strip().lower()
        if s in {"g", "kg"}:
            return MeasurementUnitType.WEIGHT
        if s in {"ml", "l"}:
            return MeasurementUnitType.VOLUME
        return MeasurementUnitType.COUNT

    def _get_or_create_unit(self, short_name: str) -> MeasurementUnit:
        short = (short_name or "").strip()
        unit = MeasurementUnit.objects.filter(short_name__iexact=short).order_by("id").first()
        if unit:
            return unit
        return MeasurementUnit.objects.create(
            name=short,
            short_name=short,
            unit_type=self._guess_unit_type(short),
        )

    def _get_or_create_ingredient(self, name: str, *, default_category: IngredientCategory) -> Ingredient:
        cleaned = (name or "").strip()
        ingredient = Ingredient.objects.filter(name__iexact=cleaned).order_by("id").first()
        if ingredient:
            return ingredient
        return Ingredient.objects.create(name=cleaned, category=default_category)

    def _to_decimal_amount(self, value) -> Decimal:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("1.00")
        if amount.is_nan() or amount <= 0:
            return Decimal("1.00")
        return amount.quantize(Decimal("0.01"))

    def _persist_ingredients(self, *, recipe: Recipe, items, default_category: IngredientCategory) -> None:
        # Merge duplicates by (ingredient_id, unit_id, group_id)
        merged: dict[tuple[int, int, int | None], dict] = {}

        for item in items:
            name = (getattr(item, "name", None) or "").strip()
            if not name:
                continue
            unit_short = (getattr(item, "unit", None) or "vnt").strip() or "vnt"
            note = (getattr(item, "note", None) or "").strip()
            amount = self._to_decimal_amount(getattr(item, "amount", 1))

            ingredient = self._get_or_create_ingredient(name, default_category=default_category)
            unit = self._get_or_create_unit(unit_short)

            key = (ingredient.id, unit.id, None)
            if key not in merged:
                merged[key] = {"amount": amount, "note": note}
            else:
                merged[key]["amount"] += amount
                if note and note not in merged[key]["note"]:
                    merged[key]["note"] = (merged[key]["note"] + "; " + note).strip("; ")

        for (ingredient_id, unit_id, group_id), data in merged.items():
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient_id=ingredient_id,
                unit_id=unit_id,
                group_id=group_id,
                amount=data["amount"],
                note=data["note"],
            )
