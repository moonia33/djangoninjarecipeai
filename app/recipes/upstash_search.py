"""Upstash Search integracija receptų indeksavimui ir paieškai.

Spec:
- Indeksuojami tik publikuoti receptai (published_at != null).
- Dokumentas mažas: neindeksuojam steps.
- Best-effort: klaidos tik log'inamos.
- Stabilus dokumento ID: recipe:<id>.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from django.db.models import Prefetch

from .models import Recipe, RecipeIngredient

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _enabled() -> bool:
    return _env_bool("UPSTASH_SEARCH_ENABLED", default=False)


def _doc_id(recipe_id: int) -> str:
    return f"recipe:{recipe_id}"


def _get_index():
    if not _enabled():
        return None

    url = os.getenv("UPSTASH_SEARCH_REST_URL", "").strip()
    token = os.getenv("UPSTASH_SEARCH_REST_TOKEN", "").strip()
    index_name = os.getenv("UPSTASH_SEARCH_INDEX", "recipes").strip() or "recipes"

    if not url or not token:
        return None

    try:
        from upstash_search import Search
    except Exception:
        logger.exception("Upstash Search SDK nerastas (pip install upstash-search)")
        return None

    try:
        client = Search(url=url, token=token, allow_telemetry=False)
        return client.index(index_name)
    except Exception:
        logger.exception("Nepavyko inicializuoti Upstash Search kliento")
        return None


def _build_recipe_document(recipe: Recipe) -> dict[str, Any]:
    ingredients: list[str] = []
    for item in recipe.recipe_ingredients.all():
        parts = [item.ingredient.name]
        if item.note:
            parts.append(item.note)
        if item.group_id:
            parts.append(item.group.name)
        ingredients.append(" ".join(parts))

    content: dict[str, Any] = {
        "title": recipe.title,
        "description": recipe.description or "",
        "meta_title": recipe.meta_title or "",
        "meta_description": recipe.meta_description or "",
        "difficulty": recipe.difficulty,
        "tags": [tag.name for tag in recipe.tags.all()],
        "categories": [cat.name for cat in recipe.categories.all()],
        "cuisines": [c.name for c in recipe.cuisines.all()],
        "meal_types": [m.name for m in recipe.meal_types.all()],
        "cooking_methods": [m.name for m in recipe.cooking_methods.all()],
        "ingredients": ingredients,
    }

    metadata: dict[str, Any] = {
        "recipe_id": recipe.id,
        "slug": recipe.slug,
        "published_at": recipe.published_at.isoformat() if recipe.published_at else None,
    }

    return {
        "id": _doc_id(recipe.id),
        "content": content,
        "metadata": metadata,
    }


def upsert_recipe(recipe_id: int) -> None:
    """Upsert'ina receptą į Upstash.

    Jei receptas nepublikuotas arba nerastas – ištrina dokumentą.
    """

    index = _get_index()
    if index is None:
        return

    try:
        recipe = (
            Recipe.objects.filter(id=recipe_id)
            .prefetch_related(
                "tags",
                "categories",
                "cuisines",
                "meal_types",
                "cooking_methods",
                Prefetch(
                    "recipe_ingredients",
                    queryset=RecipeIngredient.objects.select_related(
                        "ingredient", "unit", "group"
                    ).order_by("id"),
                ),
            )
            .first()
        )

        if recipe is None or recipe.published_at is None:
            delete_recipe(recipe_id)
            return

        doc = _build_recipe_document(recipe)
        index.upsert(documents=[doc])
    except Exception:
        logger.exception("Nepavyko suindeksuoti recepto į Upstash (recipe_id=%s)", recipe_id)


def delete_recipe(recipe_id: int) -> None:
    index = _get_index()
    if index is None:
        return

    try:
        index.delete(ids=[_doc_id(recipe_id)])
    except Exception:
        logger.exception("Nepavyko ištrinti recepto iš Upstash (recipe_id=%s)", recipe_id)


def search_recipe_ids(query: str, *, limit: int = 50) -> list[int] | None:
    """Grąžina receptų ID sąrašą pagal Upstash paiešką (relevance tvarka).

    Grąžina None, jei Upstash išjungtas arba įvyko klaida.
    """

    query = (query or "").strip()
    if not query:
        return None

    index = _get_index()
    if index is None:
        return None

    try:
        results = index.search(query=query, limit=limit)
        ids: list[int] = []
        for item in results:
            raw_id = item.id
            if raw_id.startswith("recipe:"):
                raw_id = raw_id.split(":", 1)[1]
            try:
                ids.append(int(raw_id))
            except ValueError:
                continue
        return ids
    except Exception:
        logger.exception("Upstash paieška nepavyko (query=%r)", query)
        return None
