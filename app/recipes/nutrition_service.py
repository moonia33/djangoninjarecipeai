from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator

from recipes.models import Recipe, RecipeIngredient, RecipeNutritionJob


Allergen = Literal[
    "gluten",
    "crustaceans",
    "eggs",
    "fish",
    "peanuts",
    "soy",
    "milk",
    "tree_nuts",
    "celery",
    "mustard",
    "sesame",
    "sulphites",
    "lupin",
    "molluscs",
]


class NutritionPerServing(BaseModel):
    energy_kcal: float = Field(..., ge=0)
    protein_g: float = Field(..., ge=0)
    fat_g: float = Field(..., ge=0)
    saturated_fat_g: float | None = Field(default=None, ge=0)
    carbs_g: float = Field(..., ge=0)
    sugars_g: float | None = Field(default=None, ge=0)
    fiber_g: float | None = Field(default=None, ge=0)
    salt_g: float | None = Field(default=None, ge=0)


class NutritionMicros(BaseModel):
    cholesterol_mg: float | None = Field(default=None, ge=0)
    potassium_mg: float | None = Field(default=None, ge=0)
    calcium_mg: float | None = Field(default=None, ge=0)
    iron_mg: float | None = Field(default=None, ge=0)


class NutritionResult(BaseModel):
    currency: Literal["approx"] = "approx"
    per_serving: NutritionPerServing
    micros: NutritionMicros | None = None
    allergens: list[Allergen] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    disclaimer: str

    @field_validator("allergens", mode="before")
    @classmethod
    def _normalize_allergens(cls, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, dict):
            # Accept {'gluten': true, ...} and convert to ['gluten', ...]
            items: list[str] = []
            for key, enabled in value.items():
                if enabled:
                    items.append(str(key).strip())
            return items
        return value


@dataclass(frozen=True)
class NutritionInputs:
    servings: int
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


def build_inputs(recipe: Recipe) -> NutritionInputs:
    return NutritionInputs(servings=recipe.servings, ingredients_text=_recipe_ingredients_text(recipe))


def _system_prompt() -> str:
    return (
        "Tu esi mitybos specialistas. Iš recepto ingredientų sąrašo apskaičiuok apytikslę maistinę vertę "
        "(per 1 porciją) ir nustatyk galimus EU14 alergenus. \n"
        "Svarbu: jei trūksta informacijos (pvz. 'pagal skonį'), pateik protingą prielaidą ir įrašyk į notes. \n"
        "Grąžink tik griežtą JSON (be Markdown, be teksto aplink)."
    )


def _user_prompt(inputs: NutritionInputs) -> str:
    return (
        "Recepto porcijos: "
        f"{inputs.servings}\n\n"
        "Ingredientai:\n"
        f"{inputs.ingredients_text}\n\n"
        "Reikalavimai JSON formatui:\n"
        "- currency: visada 'approx'\n"
        "- per_serving: energy_kcal, protein_g, fat_g, saturated_fat_g?, carbs_g, sugars_g?, fiber_g?, salt_g?\n"
        "- micros: cholesterol_mg?, potassium_mg?, calcium_mg?, iron_mg? (gali būti null)\n"
        "- allergens: EU14 raktai: gluten, crustaceans, eggs, fish, peanuts, soy, milk, tree_nuts, celery, mustard, sesame, sulphites, lupin, molluscs\n"
        "- notes: trumpi punktai apie prielaidas\n"
        "- disclaimer: trumpas tekstas lietuviškai, kad vertės apytikslės\n"
    )


def generate_nutrition(recipe: Recipe) -> dict[str, Any]:
    if not getattr(settings, "OPENAI_API_KEY", ""):
        raise RuntimeError("OPENAI_API_KEY nenustatytas")

    inputs = build_inputs(recipe)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Naudojam Chat Completions su JSON objektu; validaciją darom per Pydantic.
    resp = client.chat.completions.create(
        model=getattr(settings, "OPENAI_NUTRITION_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(inputs)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=getattr(settings, "OPENAI_REQUEST_TIMEOUT_SECONDS", 60),
    )

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI grąžino tuščią atsakymą")

    data = json.loads(content)
    parsed = NutritionResult.model_validate(data)

    result = parsed.model_dump()
    result["computed_at"] = timezone.now().isoformat()
    result["servings"] = inputs.servings
    return result


def compute_current_input_hash(recipe: Recipe) -> str:
    ingredient_rows = list(
        RecipeIngredient.objects.filter(recipe_id=recipe.id)
        .values_list("ingredient_id", "group_id", "unit_id", "amount", "note")
        .order_by("ingredient_id", "group_id", "unit_id", "amount", "id")
    )
    return RecipeNutritionJob.compute_input_hash(servings=recipe.servings, ingredient_rows=ingredient_rows)
