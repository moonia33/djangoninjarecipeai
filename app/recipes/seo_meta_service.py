from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, Field

from recipes.models import Recipe, RecipeIngredient


def _normalize_text(value: str | None) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_markdown(text: str) -> str:
    # Minimal, safe cleanup: remove headings/bullets/inline code and link syntax.
    text = text or ""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clip(text: str, max_len: int) -> str:
    text = _normalize_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


class SeoMetaResult(BaseModel):
    meta_title: str = Field(..., min_length=1)
    meta_description: str = Field(..., min_length=1)


@dataclass(frozen=True)
class SeoMetaInputs:
    title: str
    description: str
    difficulty: str
    preparation_time: int
    cooking_time: int
    servings: int
    cuisines: list[str]
    meal_types: list[str]
    categories: list[str]
    tags: list[str]
    cooking_methods: list[str]
    ingredients_text: str


def _recipe_ingredients_text(recipe: Recipe) -> str:
    items = (
        RecipeIngredient.objects.filter(recipe=recipe)
        .select_related("ingredient", "unit", "group")
        .order_by("group_id", "id")
    )

    lines: list[str] = []
    for ri in items:
        group = f"[{ri.group.name}] " if ri.group_id else ""
        unit = ri.unit.short_name
        note = f" ({ri.note})" if ri.note else ""
        lines.append(f"- {group}{ri.amount} {unit} {ri.ingredient.name}{note}")
    return "\n".join(lines)


def build_inputs(recipe: Recipe) -> SeoMetaInputs:
    return SeoMetaInputs(
        title=_normalize_text(recipe.title),
        description=_strip_markdown(recipe.description),
        difficulty=str(recipe.difficulty),
        preparation_time=int(recipe.preparation_time),
        cooking_time=int(recipe.cooking_time),
        servings=int(recipe.servings),
        cuisines=[c.name for c in recipe.cuisines.all()],
        meal_types=[m.name for m in recipe.meal_types.all()],
        categories=[c.name for c in recipe.categories.all()],
        tags=[t.name for t in recipe.tags.all()],
        cooking_methods=[cm.name for cm in recipe.cooking_methods.all()],
        ingredients_text=_recipe_ingredients_text(recipe),
    )


def _system_prompt() -> str:
    return (
        "Tu esi SEO specialistas receptų svetainei (LT). "
        "Iš pateikto recepto konteksto sugeneruok SEO meta laukus. "
        "Grąžink tik griežtą JSON (be Markdown, be jokio papildomo teksto).\n"
        "Taisyklės:\n"
        "- meta_title: lietuviškai, aiškus, iki 80 simbolių\n"
        "- meta_description: lietuviškai, iki 160 simbolių, be Markdown simbolių (#, *, `, nuorodų)\n"
        "- Nenaudok kabučių pradžioje/pabaigoje, nenaudok emoji\n"
        "- Jei trūksta duomenų, daryk protingas prielaidas pagal ingredientus\n"
    )


def _user_prompt(inputs: SeoMetaInputs) -> str:
    cuisines = ", ".join(inputs.cuisines[:5]) if inputs.cuisines else ""
    meal_types = ", ".join(inputs.meal_types[:5]) if inputs.meal_types else ""
    categories = ", ".join(inputs.categories[:8]) if inputs.categories else ""
    tags = ", ".join(inputs.tags[:12]) if inputs.tags else ""
    cooking_methods = ", ".join(inputs.cooking_methods[:8]) if inputs.cooking_methods else ""

    return (
        f"Pavadinimas: {inputs.title}\n"
        f"Aprašymas: {inputs.description}\n"
        f"Sudėtingumas: {inputs.difficulty}\n"
        f"Laikas: pasiruošimas {inputs.preparation_time} min, gaminimas {inputs.cooking_time} min\n"
        f"Porcijos: {inputs.servings}\n"
        f"Virtuvės: {cuisines}\n"
        f"Patiekalo tipai: {meal_types}\n"
        f"Kategorijos: {categories}\n"
        f"Žymos: {tags}\n"
        f"Gaminimo būdai: {cooking_methods}\n\n"
        "Ingredientai:\n"
        f"{inputs.ingredients_text}\n\n"
        "Grąžinamas JSON formatas:\n"
        "{\n"
        '  "meta_title": "...",\n'
        '  "meta_description": "..."\n'
        "}\n"
    )


def build_openai_chat_request(*, recipe: Recipe) -> dict[str, Any]:
    inputs = build_inputs(recipe)
    return {
        "model": getattr(settings, "OPENAI_META_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(inputs)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }


def parse_openai_chat_content_to_meta(*, content: str) -> dict[str, str]:
    data = json.loads(content)
    parsed = SeoMetaResult.model_validate(data)

    title = _clip(_strip_markdown(parsed.meta_title), 80)
    desc = _clip(_strip_markdown(parsed.meta_description), 160)

    # Final guardrails
    title = title.strip().strip('"').strip("'")
    desc = desc.strip().strip('"').strip("'")

    return {"meta_title": title, "meta_description": desc}


def generate_meta(recipe: Recipe) -> dict[str, str]:
    if not getattr(settings, "OPENAI_API_KEY", ""):
        raise RuntimeError("OPENAI_API_KEY nenustatytas")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    req = build_openai_chat_request(recipe=recipe)
    resp = client.chat.completions.create(
        **req,
        timeout=getattr(settings, "OPENAI_REQUEST_TIMEOUT_SECONDS", 60),
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI grąžino tuščią atsakymą")

    return parse_openai_chat_content_to_meta(content=content)
