from __future__ import annotations

import base64
import urllib.request
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
    fallback_model = getattr(settings, "OPENAI_IMAGE_FALLBACK_MODEL", "dall-e-3")
    size = getattr(settings, "OPENAI_IMAGE_SIZE", "1024x1024")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _call_images_generate(*, use_model: str):
        # OpenAI Images API parameter support varies by model/version.
        # Try b64 first (when supported) and gracefully retry without it.
        try:
            return client.images.generate(
                model=use_model,
                prompt=prompt,
                size=size,
                response_format="b64_json",
            )
        except Exception as exc:
            msg = str(exc)
            if "Unknown parameter" in msg and "response_format" in msg:
                return client.images.generate(
                    model=use_model,
                    prompt=prompt,
                    size=size,
                )
            raise

    try:
        resp = _call_images_generate(use_model=model)
    except Exception as exc:
        msg = str(exc)
        # Common blocker: org verification required for gpt-image-1.
        if (
            "must be verified" in msg.lower()
            or "organization" in msg.lower() and "verified" in msg.lower()
        ) and fallback_model and fallback_model != model:
            resp = _call_images_generate(use_model=fallback_model)
        else:
            raise

    data0 = getattr(resp, "data", None)
    if not data0:
        raise RuntimeError("OpenAI image atsakymas tuščias (data)")

    first = data0[0]
    b64 = getattr(first, "b64_json", None) or (first.get("b64_json") if isinstance(first, dict) else None)
    if b64:
        try:
            content = base64.b64decode(b64)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"Nepavyko dekoduoti b64: {exc}") from exc
        return GeneratedImage(content=content, content_type="image/png")

    url = getattr(first, "url", None) or (first.get("url") if isinstance(first, dict) else None)
    if url:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp2:
                content = resp2.read()
        except Exception as exc:
            raise RuntimeError(f"Nepavyko parsisiųsti vaizdo iš url: {exc}") from exc
        return GeneratedImage(content=content, content_type="image/png")

    raise RuntimeError("OpenAI image atsakymas neturi nei b64_json, nei url")
