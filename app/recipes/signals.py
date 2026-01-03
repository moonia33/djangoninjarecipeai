"""Signalai Upstash Search reindeksavimui.

Svarbu: naudojame `transaction.on_commit`, kad indeksuotume tik sėkmingai įrašytą būseną.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .models import Recipe, RecipeIngredient
from .upstash_search import delete_recipe, upsert_recipe


@receiver(post_save, sender=Recipe)
def _recipe_saved(sender, instance: Recipe, created: bool, raw: bool, **kwargs):
    if raw:
        return
    transaction.on_commit(lambda: upsert_recipe(instance.id))


@receiver(post_delete, sender=Recipe)
def _recipe_deleted(sender, instance: Recipe, **kwargs):
    transaction.on_commit(lambda: delete_recipe(instance.id))


@receiver(post_save, sender=RecipeIngredient)
def _recipe_ingredient_saved(sender, instance: RecipeIngredient, created: bool, raw: bool, **kwargs):
    if raw:
        return

    def _on_commit() -> None:
        Recipe.objects.filter(pk=instance.recipe_id).update(nutrition_dirty=True)
        upsert_recipe(instance.recipe_id)

    transaction.on_commit(_on_commit)


@receiver(post_delete, sender=RecipeIngredient)
def _recipe_ingredient_deleted(sender, instance: RecipeIngredient, **kwargs):

    def _on_commit() -> None:
        Recipe.objects.filter(pk=instance.recipe_id).update(nutrition_dirty=True)
        upsert_recipe(instance.recipe_id)

    transaction.on_commit(_on_commit)


def _reindex_on_m2m_change(instance: Recipe, action: str) -> None:
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    transaction.on_commit(lambda: upsert_recipe(instance.id))


@receiver(m2m_changed, sender=Recipe.tags.through)
def _recipe_tags_changed(sender, instance: Recipe, action: str, **kwargs):
    _reindex_on_m2m_change(instance, action)


@receiver(m2m_changed, sender=Recipe.categories.through)
def _recipe_categories_changed(sender, instance: Recipe, action: str, **kwargs):
    _reindex_on_m2m_change(instance, action)


@receiver(m2m_changed, sender=Recipe.cuisines.through)
def _recipe_cuisines_changed(sender, instance: Recipe, action: str, **kwargs):
    _reindex_on_m2m_change(instance, action)


@receiver(m2m_changed, sender=Recipe.meal_types.through)
def _recipe_meal_types_changed(sender, instance: Recipe, action: str, **kwargs):
    _reindex_on_m2m_change(instance, action)


@receiver(m2m_changed, sender=Recipe.cooking_methods.through)
def _recipe_cooking_methods_changed(sender, instance: Recipe, action: str, **kwargs):
    _reindex_on_m2m_change(instance, action)
