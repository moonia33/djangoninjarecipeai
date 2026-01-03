"""Backfill komanda Upstash Search indeksui.

Naudojimas:
- python manage.py upstash_backfill_recipes
- python manage.py upstash_backfill_recipes --limit 10
- python manage.py upstash_backfill_recipes --recipe-id 123
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from recipes.models import Recipe
from recipes.upstash_search import upsert_recipe


class Command(BaseCommand):
    help = "Suindeksuoja publikuotus receptus į Upstash Search (best-effort)."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--recipe-id", type=int, default=None)

    def handle(self, *args, **options):
        limit = options.get("limit")
        recipe_id = options.get("recipe_id")

        qs = Recipe.objects.all().order_by("id")
        if recipe_id:
            qs = qs.filter(id=recipe_id)
        else:
            qs = qs.filter(published_at__isnull=False)

        if limit:
            qs = qs[:limit]

        count = 0
        for recipe in qs:
            upsert_recipe(recipe.id)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Upstash backfill baigtas. Apdorota: {count}"))
