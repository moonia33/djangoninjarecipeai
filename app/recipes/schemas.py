"""Ninja schemos receptų API."""

from datetime import datetime
from typing import Optional

from ninja import Field, Schema


class ImageVariantSchema(Schema):
    avif: Optional[str] = None
    webp: Optional[str] = None


class ImageSetSchema(Schema):
    original: Optional[str] = None
    thumb: Optional[ImageVariantSchema] = None
    small: Optional[ImageVariantSchema] = None
    medium: Optional[ImageVariantSchema] = None
    large: Optional[ImageVariantSchema] = None


class SimpleLookupSchema(Schema):
    id: int
    name: str
    slug: Optional[str] = None


class MeasurementUnitSchema(Schema):
    id: int
    name: str
    short_name: str


class IngredientSchema(Schema):
    id: int
    name: str
    slug: Optional[str] = None


class IngredientGroupSchema(Schema):
    id: int
    name: str


class RecipeIngredientSchema(Schema):
    id: int
    group: Optional[IngredientGroupSchema] = None
    amount: float
    note: Optional[str] = None
    ingredient: IngredientSchema
    unit: MeasurementUnitSchema


class RecipeStepSchema(Schema):
    id: int
    order: int
    title: Optional[str] = None
    description: str
    note: Optional[str] = None
    duration: Optional[int] = None
    video_url: Optional[str] = None
    images: Optional[ImageSetSchema] = None


class CommentSchema(Schema):
    id: int
    content: str
    user_name: str
    is_approved: bool
    created_at: datetime


class RatingSchema(Schema):
    value: int


class RecipeSummarySchema(Schema):
    id: int
    title: str
    slug: str
    difficulty: str
    is_generated: bool = False
    images: Optional[ImageSetSchema] = None
    preparation_time: int
    cooking_time: int
    servings: int
    published_at: Optional[datetime] = None
    rating_average: Optional[float] = None
    rating_count: int
    tags: list[SimpleLookupSchema]
    is_bookmarked: bool = False


class RecipeDetailSchema(RecipeSummarySchema):
    description: Optional[str] = None
    note: Optional[str] = None
    video_url: Optional[str] = None
    nutrition: Optional[dict] = None
    nutrition_updated_at: Optional[datetime] = None
    categories: list[SimpleLookupSchema]
    meal_types: list[SimpleLookupSchema]
    cuisines: list[SimpleLookupSchema]
    cooking_methods: list[SimpleLookupSchema]
    ingredients: list[RecipeIngredientSchema]
    steps: list[RecipeStepSchema]
    comments: list[CommentSchema]
    user_rating: Optional[int] = None


class RecipeListResponse(Schema):
    total: int
    items: list[RecipeSummarySchema]


class RecipeFilters(Schema):
    search: Optional[str] = Field(
        default=None, description="Paieška pavadinime ar apraše")
    tag: Optional[str] = Field(default=None, description="Tag'o slugas")
    category: Optional[str] = Field(
        default=None, description="Kategorijos slugas")
    cuisine: Optional[str] = None
    meal_type: Optional[str] = None
    difficulty: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CommentCreateSchema(Schema):
    content: str = Field(..., min_length=3, max_length=2000)


class RatingCreateSchema(Schema):
    value: int = Field(..., ge=1, le=5)


class BookmarkToggleSchema(Schema):
    is_bookmarked: bool
