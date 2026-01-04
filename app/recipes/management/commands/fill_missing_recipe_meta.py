from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from recipes.models import Recipe
from recipes.seo_meta_service import generate_meta


def _is_blank(value: str | None) -> bool:
    return not (value or "").strip()


class Command(BaseCommand):
    help = (
        "Naktinis SEO užpildymas: jei tušti Recipe.meta_title / Recipe.meta_description, "
        "sugeneruoja per OpenAI iš recepto konteksto."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Įtraukti nepublikuotus receptus (published_at IS NULL).",
        )
        parser.add_argument(
            "--provider",
            type=str,
            choices=["openai"],
            default="openai",
            help="Meta generavimo tiekėjas. Šiuo metu palaikomas tik openai.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti kiek būtų atnaujinta.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_drafts: bool = options["include_drafts"]
        provider: str = options["provider"]
        dry_run: bool = options["dry_run"]

        if provider == "openai" and not getattr(settings, "OPENAI_API_KEY", ""):
            raise RuntimeError("OPENAI_API_KEY nenustatytas")

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
            "categories",
            "tags",
            "cooking_methods",
            "recipe_ingredients__ingredient",
            "recipe_ingredients__unit",
            "recipe_ingredients__group",
        )

        recipes = list(qs.order_by("id")[:limit])

        candidates = len(recipes)
        updated = 0
        title_filled = 0
        desc_filled = 0
        failed = 0

        for recipe in recipes:
            needs_title = _is_blank(recipe.meta_title)
            needs_desc = _is_blank(recipe.meta_description)
            if not (needs_title or needs_desc):
                continue

            try:
                generated = generate_meta(recipe)
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    f"meta_failed recipe_id={recipe.id} provider={provider} error={exc}"
                )
                continue

            new_title = generated.get("meta_title") or ""
            new_desc = generated.get("meta_description") or ""

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
                f"Recipe meta fill{suffix}: candidates={candidates} updated={updated} title_filled={title_filled} desc_filled={desc_filled} failed={failed}"
            )
        )
