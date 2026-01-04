from django.views.decorators.csrf import csrf_protect
from ninja import Router
from ninja.errors import HttpError

from .models import RecipeGenerationJob, RecipeGenerationJobStatus
from .schemas import (
    RecipeImageJobCreateRequestSchema,
    RecipeImageJobCreatedSchema,
    RecipeImageJobStatusSchema,
    RecipeGenerationJobCreatedSchema,
    RecipeGenerationJobStatusSchema,
    RecipeGenerationRequestSchema,
)

from recipes.models import Recipe, RecipeImageJob, RecipeImageJobStatus

router = Router(tags=["AI"])


@router.post("/recipe-jobs", response=RecipeGenerationJobCreatedSchema)
@csrf_protect
def create_recipe_job(request, payload: RecipeGenerationRequestSchema):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti")

    # Normalizuojam "selected_ingredient_ids" kaip sąjungą (patogu audit/analytics)
    selected_ids = sorted(set(payload.have_ingredient_ids + payload.can_buy_ingredient_ids))

    job = RecipeGenerationJob.objects.create(
        user=request.user,
        status=RecipeGenerationJobStatus.QUEUED,
        inputs=payload.dict(),
        selected_ingredient_ids=selected_ids,
    )

    return RecipeGenerationJobCreatedSchema(id=job.id, status=job.status)


@router.get("/recipe-jobs/{job_id}", response=RecipeGenerationJobStatusSchema)
def get_recipe_job(request, job_id: int):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti")

    job = RecipeGenerationJob.objects.filter(id=job_id, user=request.user).select_related("result_recipe").first()
    if not job:
        raise HttpError(404, "Job nerastas")

    result_recipe_id = job.result_recipe_id
    result_recipe_slug = job.result_recipe.slug if job.result_recipe_id else None

    return RecipeGenerationJobStatusSchema(
        id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result_recipe_id=result_recipe_id,
        result_recipe_slug=result_recipe_slug,
        error=job.error.strip() or None,
    )


@router.post("/recipe-image-jobs", response=RecipeImageJobCreatedSchema)
@csrf_protect
def create_recipe_image_job(request, payload: RecipeImageJobCreateRequestSchema):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti")

    if not payload.recipe_id and not payload.recipe_slug:
        raise HttpError(400, "Reikia nurodyti recipe_id arba recipe_slug")

    recipe_qs = Recipe.objects.all()
    if payload.recipe_id:
        recipe_qs = recipe_qs.filter(id=payload.recipe_id)
    if payload.recipe_slug:
        recipe_qs = recipe_qs.filter(slug=payload.recipe_slug)
    recipe = recipe_qs.first()
    if not recipe:
        raise HttpError(404, "Receptas nerastas")

    if not getattr(recipe, "is_generated", False):
        raise HttpError(400, "Vaizdo generavimas leidžiamas tik AI receptams")

    if getattr(recipe, "image", None):
        raise HttpError(400, "Receptas jau turi paveikslą")

    existing = (
        RecipeImageJob.objects.filter(
            recipe_id=recipe.id,
            status__in=[RecipeImageJobStatus.QUEUED, RecipeImageJobStatus.RUNNING],
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        return RecipeImageJobCreatedSchema(id=existing.id, status=existing.status)

    job = RecipeImageJob.objects.create(
        recipe_id=recipe.id,
        requested_by=request.user,
        status=RecipeImageJobStatus.QUEUED,
    )

    return RecipeImageJobCreatedSchema(id=job.id, status=job.status)


@router.get("/recipe-image-jobs/{job_id}", response=RecipeImageJobStatusSchema)
def get_recipe_image_job(request, job_id: int):
    if not request.user.is_authenticated:
        raise HttpError(401, "Reikia prisijungti")

    job = RecipeImageJob.objects.filter(id=job_id).select_related("recipe").first()
    if not job:
        raise HttpError(404, "Job nerastas")

    return RecipeImageJobStatusSchema(
        id=job.id,
        status=job.status,
        recipe_id=job.recipe_id,
        recipe_slug=job.recipe.slug,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error.strip() or None,
    )
