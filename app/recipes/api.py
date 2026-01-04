"""Ninja router'is receptams, komentarams ir įvertinimams."""

import logging
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Prefetch, Q
from django.db.models import Case, IntegerField, When
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from ninja import Query, Router
from ninja.errors import HttpError

from notifications.services import EmailTemplateNotFound, send_templated_email

from .models import (
    Bookmark,
    Comment,
    CookingMethod,
    Cuisine,
    Ingredient,
    IngredientCategory,
    MealType,
    Rating,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
    RecipeStep,
    Tag,
    Difficulty,
)
from .schemas import (
    BookmarkToggleSchema,
    CategoryListResponse,
    CategoryQuery,
    CommentCreateSchema,
    CommentSchema,
    DifficultyOptionSchema,
    ImageSetSchema,
    ImageVariantSchema,
    IngredientSchema,
    IngredientCategorySchema,
    IngredientGroupSchema,
    IngredientListResponse,
    IngredientQuery,
    IngredientWithCategorySchema,
    LookupListResponse,
    LookupQuery,
    MeasurementUnitSchema,
    RecipeFilterOptionsSchema,
    RecipeDetailSchema,
    RecipeFilters,
    RecipeIngredientSchema,
    RecipeListResponse,
    RecipeStepSchema,
    RecipeSummarySchema,
    RatingCreateSchema,
    RatingSchema,
    SimpleLookupSchema,
    CategoryFilterSchema,
)
from .upstash_search import search_recipe_ids

User = get_user_model()

router = Router(tags=["Recipes"])
logger = logging.getLogger(__name__)

IMAGE_VARIANT_ATTRS = {
    "thumb": {"avif": "image_thumb_avif", "webp": "image_thumb_webp"},
    "small": {"avif": "image_small_avif", "webp": "image_small_webp"},
    "medium": {"avif": "image_medium_avif", "webp": "image_medium_webp"},
    "large": {"avif": "image_large_avif", "webp": "image_large_webp"},
}


def _abs_media_url(request, file_field) -> str | None:
    if file_field is None:
        return None
    name = getattr(file_field, "name", None)
    if not name:
        return None

    url = None
    storage = getattr(file_field, "storage", None)
    if storage is not None:
        try:
            url = storage.url(name)
        except Exception:
            url = None

    if not url:
        try:
            url = file_field.url
        except (ValueError, FileNotFoundError, OSError):
            return None
        except Exception:
            logger.exception("Nepavyko gauti media URL (%s)", name)
            return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return request.build_absolute_uri(url)


def _simple_lookup(obj) -> SimpleLookupSchema:
    return SimpleLookupSchema(id=obj.id, name=obj.name, slug=getattr(obj, "slug", None))


def _serialize_image_set(request, obj) -> ImageSetSchema | None:
    image_field = getattr(obj, "image", None)
    original_url = _abs_media_url(request, image_field)
    variants: dict[str, ImageVariantSchema] = {}
    has_variant = False
    for size, mapping in IMAGE_VARIANT_ATTRS.items():
        avif_spec = getattr(obj, mapping["avif"], None)
        webp_spec = getattr(obj, mapping["webp"], None)
        avif_url = _abs_media_url(request, avif_spec)
        webp_url = _abs_media_url(request, webp_spec)
        if avif_url or webp_url:
            has_variant = True
        variants[size] = ImageVariantSchema(avif=avif_url, webp=webp_url)
    if not original_url and not has_variant:
        return None
    return ImageSetSchema(
        original=original_url,
        thumb=variants.get("thumb"),
        small=variants.get("small"),
        medium=variants.get("medium"),
        large=variants.get("large"),
    )


def _serialize_recipe_summary(request, recipe: Recipe, bookmarked_ids: set[int]) -> RecipeSummarySchema:
    rating_average = getattr(recipe, "rating_average", None)
    rating_count = getattr(recipe, "rating_count", 0) or 0
    return RecipeSummarySchema(
        id=recipe.id,
        title=recipe.title,
        slug=recipe.slug,
        difficulty=recipe.difficulty,
        is_generated=getattr(recipe, "is_generated", False),
        images=_serialize_image_set(request, recipe),
        preparation_time=recipe.preparation_time,
        cooking_time=recipe.cooking_time,
        servings=recipe.servings,
        published_at=recipe.published_at,
        rating_average=float(
            rating_average) if rating_average is not None else None,
        rating_count=rating_count,
        tags=[_simple_lookup(tag) for tag in recipe.tags.all()],
        is_bookmarked=recipe.id in bookmarked_ids,
    )


def _serialize_ingredients(recipe: Recipe) -> list[RecipeIngredientSchema]:
    items: list[RecipeIngredientSchema] = []
    for ingredient in recipe.recipe_ingredients.all():
        ingredient_schema = IngredientSchema(
            id=ingredient.ingredient.id,
            name=ingredient.ingredient.name,
            slug=ingredient.ingredient.slug,
        )
        unit_schema = MeasurementUnitSchema(
            id=ingredient.unit.id,
            name=ingredient.unit.name,
            short_name=ingredient.unit.short_name,
        )

        group_schema = (
            IngredientGroupSchema(id=ingredient.group.id, name=ingredient.group.name)
            if ingredient.group_id
            else None
        )
        items.append(
            RecipeIngredientSchema(
                id=ingredient.id,
                group=group_schema,
                amount=float(ingredient.amount),
                note=ingredient.note or None,
                ingredient=ingredient_schema,
                unit=unit_schema,
            )
        )
    return items


def _serialize_steps(request, recipe: Recipe) -> list[RecipeStepSchema]:
    return [
        RecipeStepSchema(
            id=step.id,
            order=step.order,
            title=step.title or None,
            description=step.description,
            note=getattr(step, "note", "") or None,
            duration=step.duration,
            video_url=step.video_url or None,
            images=_serialize_image_set(request, step),
        )
        for step in recipe.steps.all()
    ]


def _user_display(user: User | None) -> str:
    if not user:
        return "Anonimas"
    full_name = user.get_full_name()
    if full_name:
        return full_name
    if user.email:
        return user.email
    return user.get_username()


def _serialize_comment(comment: Comment) -> CommentSchema:
    return CommentSchema(
        id=comment.id,
        content=comment.content,
        user_name=_user_display(
            comment.user if hasattr(comment, "user") else None),
        is_approved=comment.is_approved,
        created_at=comment.created_at,
    )


def _serialize_comments(comments: Iterable[Comment], viewer: User | None) -> list[CommentSchema]:
    viewer_id = viewer.id if viewer else None
    items: list[CommentSchema] = []
    for comment in comments:
        if not comment.is_approved and comment.user_id != viewer_id:
            continue
        items.append(_serialize_comment(comment))
    return items


def _notify_comment_submission(request, comment: Comment) -> None:
    recipients = getattr(settings, "COMMENT_NOTIFICATION_RECIPIENTS", [])
    if not recipients:
        return

    try:
        admin_url = request.build_absolute_uri(
            reverse("admin:recipes_comment_change", args=[comment.pk])
        )
    except Exception:  # pragma: no cover - fallback jei request nepasiekiamas
        admin_url = ""

    context = {
        "recipe_title": comment.recipe.title,
        "author_name": _user_display(comment.user),
        "content": comment.content,
        "admin_url": admin_url,
        "created_at": comment.created_at,
    }

    try:
        send_templated_email(
            key="comment_notification",
            recipients=recipients,
            context=context,
        )
    except EmailTemplateNotFound:
        logger.warning(
            "Nerastas 'comment_notification' šablonas – admins neinformuoti (comment_id=%s)",
            comment.pk,
        )
    except Exception:  # pragma: no cover - gynybinis log'as
        logger.exception(
            "Nepavyko informuoti admino apie komentarą (comment_id=%s)",
            comment.pk,
        )


def _prefetch_for_list(qs):
    return qs.prefetch_related("tags")


def _prefetch_for_detail(qs):
    return qs.prefetch_related(
        "tags",
        "categories",
        "meal_types",
        "cuisines",
        "cooking_methods",
        Prefetch(
            "recipe_ingredients",
            queryset=RecipeIngredient.objects.select_related(
                "ingredient", "unit", "group").order_by("id"),
        ),
        Prefetch("steps", queryset=RecipeStep.objects.order_by("order")),
        Prefetch("comments", queryset=Comment.objects.select_related(
            "user").order_by("-created_at")),
    )


@router.get("/filters", response=RecipeFilterOptionsSchema)
def get_filter_options(request):
    """Frontendui: grąžina visus galimus filtrų pasirinkimus vienu request'u."""

    cuisines = [SimpleLookupSchema(id=c.id, name=c.name, slug=c.slug) for c in Cuisine.objects.order_by("name")]
    meal_types = [
        SimpleLookupSchema(id=m.id, name=m.name, slug=m.slug) for m in MealType.objects.order_by("name")
    ]
    cooking_methods = [
        SimpleLookupSchema(id=m.id, name=m.name, slug=m.slug)
        for m in CookingMethod.objects.order_by("name")
    ]
    difficulties = [
        DifficultyOptionSchema(key=key, label=label)
        for key, label in Difficulty.choices
    ]

    return RecipeFilterOptionsSchema(
        cuisines=cuisines,
        meal_types=meal_types,
        cooking_methods=cooking_methods,
        difficulties=difficulties,
    )


def _paginate_lookup_queryset(qs, *, search: str | None, limit: int, offset: int):
    if search:
        qs = qs.filter(name__icontains=search)
    total = qs.count()
    items = list(qs.order_by("name")[offset : offset + limit])
    return total, items


@router.get("/tags", response=LookupListResponse)
def list_tags(request, filters: LookupQuery = Query(...)):
    qs = Tag.objects.all()
    total, items = _paginate_lookup_queryset(
        qs,
        search=filters.search,
        limit=filters.limit,
        offset=filters.offset,
    )
    return LookupListResponse(total=total, items=[_simple_lookup(t) for t in items])


@router.get("/categories", response=CategoryListResponse)
def list_categories(request, filters: CategoryQuery = Query(...)):
    qs = RecipeCategory.objects.all()
    if filters.parent_id is not None:
        qs = qs.filter(parent_id=filters.parent_id)
    elif filters.root_only:
        qs = qs.filter(parent_id__isnull=True)

    if filters.search:
        qs = qs.filter(name__icontains=filters.search)

    total = qs.count()
    batch = list(qs.order_by("name")[filters.offset : filters.offset + filters.limit])
    items = [
        CategoryFilterSchema(id=c.id, name=c.name, slug=c.slug, parent_id=c.parent_id)
        for c in batch
    ]
    return CategoryListResponse(total=total, items=items)


@router.get("/cuisines", response=LookupListResponse)
def list_cuisines(request, filters: LookupQuery = Query(...)):
    qs = Cuisine.objects.all()
    total, items = _paginate_lookup_queryset(
        qs,
        search=filters.search,
        limit=filters.limit,
        offset=filters.offset,
    )
    return LookupListResponse(total=total, items=[_simple_lookup(c) for c in items])


@router.get("/meal-types", response=LookupListResponse)
def list_meal_types(request, filters: LookupQuery = Query(...)):
    qs = MealType.objects.all()
    total, items = _paginate_lookup_queryset(
        qs,
        search=filters.search,
        limit=filters.limit,
        offset=filters.offset,
    )
    return LookupListResponse(total=total, items=[_simple_lookup(m) for m in items])


@router.get("/cooking-methods", response=LookupListResponse)
def list_cooking_methods(request, filters: LookupQuery = Query(...)):
    qs = CookingMethod.objects.all()
    total, items = _paginate_lookup_queryset(
        qs,
        search=filters.search,
        limit=filters.limit,
        offset=filters.offset,
    )
    return LookupListResponse(total=total, items=[_simple_lookup(m) for m in items])


@router.get("/ingredient-categories", response=CategoryListResponse)
def list_ingredient_categories(request, filters: CategoryQuery = Query(...)):
    qs = IngredientCategory.objects.all()
    if filters.parent_id is not None:
        qs = qs.filter(parent_id=filters.parent_id)
    elif filters.root_only:
        qs = qs.filter(parent_id__isnull=True)

    if filters.search:
        qs = qs.filter(name__icontains=filters.search)

    total = qs.count()
    batch = list(qs.order_by("name")[filters.offset : filters.offset + filters.limit])
    items = [
        CategoryFilterSchema(id=c.id, name=c.name, slug=c.slug, parent_id=c.parent_id)
        for c in batch
    ]
    return CategoryListResponse(total=total, items=items)


@router.get("/ingredients", response=IngredientListResponse)
def list_ingredients(request, filters: IngredientQuery = Query(...)):
    qs = Ingredient.objects.select_related("category")
    if filters.category:
        qs = qs.filter(category__slug=filters.category)

    if filters.search:
        qs = qs.filter(name__icontains=filters.search)

    total = qs.count()
    batch = list(qs.order_by("name")[filters.offset : filters.offset + filters.limit])
    items = [
        IngredientWithCategorySchema(
            id=i.id,
            name=i.name,
            slug=i.slug,
            category=IngredientCategorySchema(
                id=i.category.id,
                name=i.category.name,
                slug=i.category.slug,
                parent_id=i.category.parent_id,
            ),
        )
        for i in batch
    ]
    return IngredientListResponse(total=total, items=items)


def _annotate_with_ratings(qs):
    return qs.annotate(
        rating_average=Avg("ratings__value"),
        rating_count=Count("ratings", distinct=True),
    )


@router.get("/", response=RecipeListResponse)
def list_recipes(request, filters: RecipeFilters = Query(...)):
    qs = Recipe.objects.all()

    if filters.tag:
        qs = qs.filter(tags__slug=filters.tag)
    if filters.category:
        qs = qs.filter(categories__slug=filters.category)
    if filters.cuisine:
        qs = qs.filter(cuisines__slug=filters.cuisine)
    if filters.meal_type:
        qs = qs.filter(meal_types__slug=filters.meal_type)
    if filters.difficulty:
        qs = qs.filter(difficulty=filters.difficulty)

    used_upstash = False
    candidate_ids: list[int] | None = None
    if filters.search and filters.offset < 1000:
        candidate_limit = min(max(filters.limit + filters.offset, 20), 1000)
        candidate_ids = search_recipe_ids(filters.search, limit=candidate_limit)
        if candidate_ids:
            used_upstash = True
            qs = qs.filter(id__in=candidate_ids)
        else:
            candidate_ids = None

    if filters.search and not used_upstash:
        qs = qs.filter(
            Q(title__icontains=filters.search)
            | Q(description__icontains=filters.search)
        )

    qs = _annotate_with_ratings(qs)

    if used_upstash and candidate_ids:
        ordering = Case(
            *[When(id=pk, then=pos) for pos, pk in enumerate(candidate_ids)],
            output_field=IntegerField(),
        )
        qs = qs.order_by(ordering)
    else:
        qs = qs.order_by("-published_at", "-updated_at", "-id")

    qs = qs.distinct()

    total = qs.count()
    qs = _prefetch_for_list(qs)
    start = filters.offset
    end = start + filters.limit
    recipes_batch = list(qs[start:end])

    bookmarked_ids: set[int] = set()
    if request.user.is_authenticated and recipes_batch:
        recipe_ids = [recipe.id for recipe in recipes_batch]
        bookmarked_ids = set(
            Bookmark.objects.filter(
                user=request.user, recipe_id__in=recipe_ids)
            .values_list("recipe_id", flat=True)
        )

    items = [
        _serialize_recipe_summary(request, recipe, bookmarked_ids)
        for recipe in recipes_batch
    ]

    return RecipeListResponse(total=total, items=items)


@router.get("/bookmarks", response=RecipeListResponse)
def list_bookmarks(request):
    if not request.user.is_authenticated:
        raise HttpError(
            401, "Reikia prisijungti, kad matytumėte išsaugotus receptus")

    qs = (
        Recipe.objects.filter(bookmarks__user=request.user)
        .order_by("-bookmarks__created_at")
        .distinct()
    )
    qs = _annotate_with_ratings(qs)
    qs = _prefetch_for_list(qs)

    recipes_batch = list(qs)
    bookmarked_ids = {recipe.id for recipe in recipes_batch}

    items = [
        _serialize_recipe_summary(request, recipe, bookmarked_ids)
        for recipe in recipes_batch
    ]
    return RecipeListResponse(total=len(items), items=items)


@router.get("/{slug}", response=RecipeDetailSchema)
def get_recipe_detail(request, slug: str):
    qs = Recipe.objects.filter(slug=slug)
    qs = _annotate_with_ratings(qs)
    qs = _prefetch_for_detail(qs)
    recipe = get_object_or_404(qs)

    user = request.user if request.user.is_authenticated else None
    is_bookmarked = False
    user_rating_value = None
    if user:
        is_bookmarked = Bookmark.objects.filter(
            user=user, recipe=recipe).exists()
        user_rating = Rating.objects.filter(user=user, recipe=recipe).first()
        if user_rating:
            user_rating_value = user_rating.value

    summary = _serialize_recipe_summary(
        request, recipe, {recipe.id} if is_bookmarked else set())
    summary_data = summary.dict()
    summary_data["is_bookmarked"] = is_bookmarked

    return RecipeDetailSchema(
        **summary_data,
        meta_title=recipe.meta_title or None,
        meta_description=recipe.meta_description or None,
        description=recipe.description or None,
        note=getattr(recipe, "note", "") or None,
        video_url=recipe.video_url or None,
        nutrition=getattr(recipe, "nutrition", None),
        nutrition_updated_at=getattr(recipe, "nutrition_updated_at", None),
        categories=[_simple_lookup(cat) for cat in recipe.categories.all()],
        meal_types=[_simple_lookup(mt) for mt in recipe.meal_types.all()],
        cuisines=[_simple_lookup(cuisine)
                  for cuisine in recipe.cuisines.all()],
        cooking_methods=[_simple_lookup(method)
                         for method in recipe.cooking_methods.all()],
        ingredients=_serialize_ingredients(recipe),
        steps=_serialize_steps(request, recipe),
        comments=_serialize_comments(recipe.comments.all(), user),
        user_rating=user_rating_value,
    )


@router.post("/{recipe_id}/bookmark", response=BookmarkToggleSchema)
@csrf_protect
def toggle_bookmark(request, recipe_id: int):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti, kad išsaugotumėte receptus")

    recipe = get_object_or_404(Recipe, pk=recipe_id)
    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user, recipe=recipe
    )
    if not created:
        bookmark.delete()
        return BookmarkToggleSchema(is_bookmarked=False)
    return BookmarkToggleSchema(is_bookmarked=True)


@router.post("/{recipe_id}/comments", response=CommentSchema)
@csrf_protect
def create_comment(request, recipe_id: int, payload: CommentCreateSchema):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti, kad komentuotumėte")

    recipe = get_object_or_404(Recipe, pk=recipe_id)
    comment = Comment.objects.create(
        user=request.user,
        recipe=recipe,
        content=payload.content,
    )
    _notify_comment_submission(request, comment)
    return _serialize_comment(comment)


@router.post("/{recipe_id}/rating", response=RatingSchema)
@csrf_protect
def upsert_rating(request, recipe_id: int, payload: RatingCreateSchema):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti, kad vertintumėte receptą")

    recipe = get_object_or_404(Recipe, pk=recipe_id)
    rating, _ = Rating.objects.update_or_create(
        user=request.user,
        recipe=recipe,
        defaults={"value": payload.value},
    )
    return RatingSchema(value=rating.value)
