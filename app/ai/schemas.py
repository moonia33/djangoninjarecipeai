from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from ninja import Field, Schema


DishType = Literal["desertas", "antras", "sriuba", "saltas_uzkandis"]
PrepSpeed = Literal["greitas", "iprastas"]


class RecipeGenerationRequestSchema(Schema):
    dish_type: DishType

    have_ingredient_ids: list[int] = Field(default_factory=list)
    have_ingredients_text: list[str] = Field(default_factory=list)

    can_buy_ingredient_ids: list[int] = Field(default_factory=list)
    can_buy_ingredients_text: list[str] = Field(default_factory=list)

    prep_speed: PrepSpeed

    exclude: list[str] = Field(default_factory=list, description="Griežti draudimai (pvz. 'svogūnai', 'česnakai', 'laktozė')")


class RecipeGenerationJobCreatedSchema(Schema):
    id: int
    status: str


class RecipeGenerationJobStatusSchema(Schema):
    id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    result_recipe_id: Optional[int] = None
    result_recipe_slug: Optional[str] = None

    error: Optional[str] = None
