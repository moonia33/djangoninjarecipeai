from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from recipes.models import Ingredient


DifficultyKey = Literal["easy", "medium", "hard"]


class GeneratedStep(BaseModel):
    order: int = Field(..., ge=1)
    title: str | None = None
    description: str = Field(..., min_length=1)
    duration: int | None = Field(default=None, ge=0)


class GeneratedRecipe(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, description="Markdown")
    ingredients: list[str] = Field(default_factory=list, description="Markdown bullet lines without leading section title")
    steps: list[GeneratedStep]

    preparation_time: int = Field(..., ge=0)
    cooking_time: int = Field(..., ge=0)
    servings: int = Field(..., ge=1, le=20)
    difficulty: DifficultyKey

    note: str | None = Field(default=None, description="Optional Markdown")

    @field_validator("ingredients", mode="before")
    @classmethod
    def _normalize_ingredients(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            # Accept a single markdown block and split lines
            lines = [ln.strip() for ln in value.splitlines()]
            return [ln.lstrip("- ").strip() for ln in lines if ln.strip()]
        return value


@dataclass(frozen=True)
class GenerationInputs:
    dish_type: str
    have_ingredients: list[str]
    can_buy_ingredients: list[str]
    exclude: list[str]
    prep_speed: str


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _system_prompt() -> str:
    return (
        "Tu esi receptų kūrėjas (LT). Sugeneruok vieną aiškų, įgyvendinamą receptą pagal įvestį. "
        "Svarbu: grąžink tik griežtą JSON (be Markdown aplink JSON, be jokio papildomo teksto).\n"
        "Taisyklės:\n"
        "- 'exclude' yra GRIEŽTI draudimai: negali pasirodyti nei ingredientuose, nei žingsniuose (nei sinonimais).\n"
        "- Ingredientų sąrašas turi būti realistiškas; galima siūlyti papildomų ingredientų, jei vartotojas gali nupirkti.\n"
        "- 'ingredients' grąžink kaip sąrašą trumpų eilučių (be skyriaus antraštės), skirtų atvaizduoti bullet list.\n"
        "- 'description' ir 'note' yra Markdown.\n"
        "- 'difficulty' privalo būti vienas iš: easy, medium, hard.\n"
    )


def _user_prompt(inputs: GenerationInputs) -> str:
    have = "\n".join(f"- {x}" for x in inputs.have_ingredients) or "- (nieko konkretaus)"
    can_buy = "\n".join(f"- {x}" for x in inputs.can_buy_ingredients) or "- (laisvai)"
    exclude = ", ".join(inputs.exclude) if inputs.exclude else "(nėra)"

    return (
        f"Patiekalo tipas: {inputs.dish_type}\n"
        f"Paruošimo tempas: {inputs.prep_speed}\n"
        f"Turiu namuose (prioritetas naudoti):\n{have}\n\n"
        f"Galiu nupirkti (galima naudoti laisvai):\n{can_buy}\n\n"
        f"GRIEŽTAI draudžiama (exclude): {exclude}\n\n"
        "Grąžinamas JSON formatas:\n"
        "{\n"
        '  "title": "...",\n'
        '  "description": "... (Markdown)",\n'
        '  "ingredients": ["...", "..."],\n'
        '  "steps": [{"order": 1, "title": "...", "description": "... (Markdown)", "duration": 10}],\n'
        '  "preparation_time": 10,\n'
        '  "cooking_time": 20,\n'
        '  "servings": 2,\n'
        '  "difficulty": "easy",\n'
        '  "note": "... (Markdown, optional)"\n'
        "}\n"
    )


def build_inputs_from_payload(payload: dict[str, Any]) -> GenerationInputs:
    def _as_list(value) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    have_ids = [int(x) for x in _as_list(payload.get("have_ingredient_ids")) if str(x).strip()]
    can_buy_ids = [int(x) for x in _as_list(payload.get("can_buy_ingredient_ids")) if str(x).strip()]

    id_set = sorted(set(have_ids + can_buy_ids))
    id_to_name: dict[int, str] = {
        row["id"]: row["name"]
        for row in Ingredient.objects.filter(id__in=id_set).values("id", "name")
    }

    have_text = [_normalize_text(x) for x in _as_list(payload.get("have_ingredients_text")) if _normalize_text(x)]
    can_buy_text = [_normalize_text(x) for x in _as_list(payload.get("can_buy_ingredients_text")) if _normalize_text(x)]

    have = [id_to_name[i] for i in have_ids if i in id_to_name] + have_text
    can_buy = [id_to_name[i] for i in can_buy_ids if i in id_to_name] + can_buy_text

    exclude = [_normalize_text(x) for x in _as_list(payload.get("exclude")) if _normalize_text(x)]

    return GenerationInputs(
        dish_type=str(payload.get("dish_type") or ""),
        prep_speed=str(payload.get("prep_speed") or ""),
        have_ingredients=have,
        can_buy_ingredients=can_buy,
        exclude=exclude,
    )


def build_openai_chat_request(*, inputs: GenerationInputs) -> dict[str, Any]:
    return {
        "model": getattr(settings, "OPENAI_RECIPE_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(inputs)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
    }


def parse_openai_chat_content_to_recipe(*, content: str) -> GeneratedRecipe:
    data = json.loads(content)
    # Minimal cleanup if model returns unexpected whitespace
    if isinstance(data, dict) and "title" in data:
        data["title"] = _normalize_text(str(data.get("title")))
    return GeneratedRecipe.model_validate(data)


def generate_recipe_from_payload(*, payload: dict[str, Any]) -> tuple[GeneratedRecipe, dict[str, Any] | None]:
    if not getattr(settings, "OPENAI_API_KEY", ""):
        raise RuntimeError("OPENAI_API_KEY nenustatytas")

    inputs = build_inputs_from_payload(payload)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    req = build_openai_chat_request(inputs=inputs)
    resp = client.chat.completions.create(
        **req,
        timeout=getattr(settings, "OPENAI_REQUEST_TIMEOUT_SECONDS", 60),
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI grąžino tuščią atsakymą")

    token_usage = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        try:
            token_usage = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        except Exception:
            token_usage = None

    return parse_openai_chat_content_to_recipe(content=content), token_usage
