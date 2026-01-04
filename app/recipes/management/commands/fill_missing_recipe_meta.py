from __future__ import annotations

import re
import textwrap
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.html import strip_tags

from recipes.models import Recipe


def _is_blank(value: str | None) -> bool:
    return not (value or "").strip()


def _normalize_text(value: str | None) -> str:
    text = strip_tags(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clip(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= max_len:
        return text

    shortened = textwrap.shorten(text, width=max_len, placeholder="")
    shortened = shortened.strip()
    if shortened:
        return shortened
    return text[:max_len].rstrip()


def _uniq_names(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        v = (value or "").strip()
        if not v:
            continue
        key = v.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _build_meta_title(recipe: Recipe) -> str:
    base = _normalize_text(recipe.title) or "Receptas"

    cuisines = _uniq_names([c.name for c in recipe.cuisines.all()])
    meal_types = _uniq_names([m.name for m in recipe.meal_types.all()])

    suffix = ""
    if cuisines:
        suffix = cuisines[0]
    elif meal_types:
        suffix = meal_types[0]

    if suffix:
        candidate = f"{base} – {suffix}"
        if len(candidate) <= 80:
            return candidate

    return _clip(base, 80)


def _build_meta_description(recipe: Recipe) -> str:
    description = _normalize_text(recipe.description)
    if description:
        return _clip(description, 160)

    cuisines = _uniq_names([c.name for c in recipe.cuisines.all()])
    meal_types = _uniq_names([m.name for m in recipe.meal_types.all()])

    ingredient_names = _uniq_names(
        [ri.ingredient.name for ri in recipe.recipe_ingredients.all() if ri.ingredient_id]
    )

    context_bits: list[str] = []
    if cuisines:
        context_bits.append(", ".join(cuisines[:2]))
    if meal_types:
        context_bits.append(", ".join(meal_types[:2]))

    intro = _normalize_text(recipe.title) or "Receptas"
    if context_bits:
        intro = f"{intro} ({' / '.join(context_bits)})"

    parts: list[str] = [f"{intro}."]

    if ingredient_names:
        parts.append(f"Ingredientai: {', '.join(ingredient_names[:8])}.")

    parts.append(
        f"Paruošimas {recipe.preparation_time} min, gaminimas {recipe.cooking_time} min, {recipe.servings} porc."
    )

    return _clip(" ".join(parts), 160)


class Command(BaseCommand):
    help = "Naktinis SEO užpildymas: jei tušti Recipe.meta_title / Recipe.meta_description, sugeneruoja iš recepto konteksto."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Įtraukti nepublikuotus receptus (published_at IS NULL).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti kiek būtų atnaujinta.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_drafts: bool = options["include_drafts"]
        dry_run: bool = options["dry_run"]

        qs = Recipe.objects.all()
        if not include_drafts:
            qs = qs.filter(published_at__isnull=False)

        qs = qs.filter(
            Q(meta_title="")
            | Q(meta_title__isnull=True)
            | Q(meta_description="")
            | Q(meta_description__isnull=True)
        ).prefetch_related(
            "cuisines",
            "meal_types",
            "recipe_ingredients__ingredient",
        )

        recipes = list(qs.order_by("id")[:limit])

        candidates = len(recipes)
        updated = 0
        title_filled = 0
        desc_filled = 0

        for recipe in recipes:
            needs_title = _is_blank(recipe.meta_title)
            needs_desc = _is_blank(recipe.meta_description)
            if not (needs_title or needs_desc):
                continue

            new_title = recipe.meta_title
            new_desc = recipe.meta_description

            if needs_title:
                new_title = _build_meta_title(recipe)
            if needs_desc:
                new_desc = _build_meta_description(recipe)

            if dry_run:
                updated += 1
                if needs_title:
                    title_filled += 1
                if needs_desc:
                    desc_filled += 1
                continue

            now = timezone.now()
            updates: dict[str, object] = {"updated_at": now}
            if needs_title:
                updates["meta_title"] = new_title
            if needs_desc:
                updates["meta_description"] = new_desc

            Recipe.objects.filter(pk=recipe.pk).update(**updates)
            updated += 1
            if needs_title:
                title_filled += 1
            if needs_desc:
                desc_filled += 1

        suffix = " (DRY-RUN)" if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Recipe meta fill{suffix}: candidates={candidates} updated={updated} title_filled={title_filled} desc_filled={desc_filled}"
            )
        )
