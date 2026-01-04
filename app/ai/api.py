from __future__ import annotations

from django.views.decorators.csrf import csrf_protect
from ninja import Router
from ninja.errors import HttpError

from .models import RecipeGenerationJob, RecipeGenerationJobStatus
from .schemas import (
    RecipeGenerationJobCreatedSchema,
    RecipeGenerationJobStatusSchema,
    RecipeGenerationRequestSchema,
)

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
