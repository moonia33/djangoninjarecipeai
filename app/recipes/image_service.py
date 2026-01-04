from __future__ import annotations

import base64
from dataclasses import dataclass

from django.conf import settings
from openai import OpenAI

from recipes.models import Recipe


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    content_type: str


def build_recipe_image_prompt(*, recipe: Recipe) -> str:
    """Build a compact prompt for a recipe hero image.

    Intentionally avoids long context; image generation works best with short, specific prompts.
    """

    ingredient_names = list(
        recipe.recipe_ingredients.select_related("ingredient")
        .order_by("id")
        .values_list("ingredient__name", flat=True)[:6]
    )
    ingredients_part = ", ".join(str(x) for x in ingredient_names if str(x).strip())

    parts: list[str] = [
        "High-quality food photography of a finished dish",
        f"Dish name: {recipe.title}",
    ]

    if ingredients_part:
        parts.append(f"Key ingredients: {ingredients_part}")

    parts.extend(
        [
            "Natural light, appetizing, clean background",
            "Top-down or 3/4 angle, shallow depth of field",
            "No text, no watermark, no logo",
        ]
    )

    return ". ".join(parts).strip() + "."


def generate_recipe_image(*, prompt: str) -> GeneratedImage:
    if not getattr(settings, "OPENAI_API_KEY", ""):
        raise RuntimeError("OPENAI_API_KEY nenustatytas")

    model = getattr(settings, "OPENAI_IMAGE_MODEL", "gpt-image-1")
    size = getattr(settings, "OPENAI_IMAGE_SIZE", "1024x1024")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Prefer base64 output so we can store it directly to our storage.
    resp = client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        response_format="b64_json",
    )

    data0 = getattr(resp, "data", None)
    if not data0:
        raise RuntimeError("OpenAI image atsakymas tuščias (data)")

    first = data0[0]
    b64 = getattr(first, "b64_json", None) or (first.get("b64_json") if isinstance(first, dict) else None)
    if not b64:
        raise RuntimeError("OpenAI image atsakymas neturi b64_json")

    try:
        content = base64.b64decode(b64)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"Nepavyko dekoduoti b64: {exc}") from exc

    return GeneratedImage(content=content, content_type="image/png")
