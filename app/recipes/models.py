"""Domeno modeliai receptų platformai."""

import hashlib
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit


def _generate_unique_slug(instance: models.Model, value: str, *, field_name: str = "slug") -> str:
    """Sugeneruoja unikalų slug lauką, kad vengti dublikatų."""

    base_slug = slugify(value) or slugify(uuid4().hex)
    slug_value = base_slug
    ModelClass = instance.__class__
    counter = 1

    while ModelClass.objects.filter(**{field_name: slug_value}).exclude(pk=instance.pk).exists():
        slug_value = f"{base_slug}-{counter}"
        counter += 1

    return slug_value


class TimeStampedModel(models.Model):
    """Bazinė klasė su `created_at` ir `updated_at`."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NamedSluggedModel(TimeStampedModel):
    """Pagalbinė bazė modeliams su `name` ir `slug`."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover - paprastas vaizdavimas
        return self.name


class Difficulty(models.TextChoices):
    EASY = "easy", "Lengva"
    MEDIUM = "medium", "Vidutinė"
    HARD = "hard", "Sudėtinga"


class MeasurementUnitType(models.TextChoices):
    WEIGHT = "weight", "Svoris"
    VOLUME = "volume", "Tūris"
    COUNT = "count", "Vnt. skaičius"


class IngredientCategory(NamedSluggedModel):
    """Hierarchinė ingredientų kategorijų struktūra."""

    parent = models.ForeignKey(
        "self",
        related_name="children",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = "Ingrediento kategorija"
        verbose_name_plural = "Ingredientų kategorijos"


class RecipeCategory(NamedSluggedModel):
    """Hierarchinės receptų kategorijos."""

    parent = models.ForeignKey(
        "self",
        related_name="children",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = "Recepto kategorija"
        verbose_name_plural = "Receptų kategorijos"


class Ingredient(NamedSluggedModel):
    """Bazinis ingredientų katalogas."""

    category = models.ForeignKey(
        IngredientCategory,
        related_name="ingredients",
        on_delete=models.PROTECT,
    )

    class Meta:
        ordering = ["name"]


class IngredientGroup(TimeStampedModel):
    """Pagalbinė recepto ingredientų grupė (pvz., "Padažui", "Tešlai")."""

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Ingredientų grupė"
        verbose_name_plural = "Ingredientų grupės"
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover
        return self.name


class MeasurementUnit(TimeStampedModel):
    """Matavimo vienetų sąrašas (pvz., gramai, mililitrai)."""

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=10)
    unit_type = models.CharField(
        max_length=20, choices=MeasurementUnitType.choices)

    class Meta:
        verbose_name = "Matavimo vienetas"
        verbose_name_plural = "Matavimo vienetai"
        unique_together = ("name", "short_name")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.short_name})"


class MealType(NamedSluggedModel):
    """Paros metu vartojamo patiekalo tipai (pusryčiai, pietūs...)."""

    pass


class Cuisine(NamedSluggedModel):
    """Virtuvės tipai pagal regionus."""

    region = models.CharField(max_length=255, blank=True)


class CookingMethod(NamedSluggedModel):
    """Maisto paruošimo būdai (kepimas, BBQ ir pan.)."""

    pass


class Tag(NamedSluggedModel):
    """Laisvos formos žymos greitam filtravimui."""

    pass


class Recipe(TimeStampedModel):
    """Pagrindinis recepto objektas."""

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    meta_title = models.CharField(max_length=80, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    note = models.TextField(blank=True)
    is_generated = models.BooleanField(default=False)

    nutrition = models.JSONField(null=True, blank=True)
    nutrition_updated_at = models.DateTimeField(null=True, blank=True)
    nutrition_input_hash = models.CharField(max_length=64, blank=True, default="")
    nutrition_dirty = models.BooleanField(default=True)
    nutrition_last_enqueued_at = models.DateTimeField(null=True, blank=True)
    preparation_time = models.PositiveIntegerField(
        help_text="Minutės pasiruošimui")
    cooking_time = models.PositiveIntegerField(help_text="Minutės gaminimui")
    servings = models.PositiveSmallIntegerField(default=1)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices)
    image = models.ImageField(upload_to="recipes/hero/", blank=True, null=True)
    image_thumb_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFill(250, 250)],
        format="AVIF",
        options={"quality": 80},
    )
    image_thumb_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFill(250, 250)],
        format="WEBP",
        options={"quality": 80},
    )
    image_small_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=320)],
        format="AVIF",
        options={"quality": 80},
    )
    image_small_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=320)],
        format="WEBP",
        options={"quality": 80},
    )
    image_medium_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=768)],
        format="AVIF",
        options={"quality": 82},
    )
    image_medium_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=768)],
        format="WEBP",
        options={"quality": 82},
    )
    image_large_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=1280)],
        format="AVIF",
        options={"quality": 85},
    )
    image_large_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=1280)],
        format="WEBP",
        options={"quality": 85},
    )
    video_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    categories = models.ManyToManyField(
        RecipeCategory, blank=True, related_name="recipes")
    tags = models.ManyToManyField(Tag, blank=True, related_name="recipes")
    cuisines = models.ManyToManyField(
        Cuisine, blank=True, related_name="recipes")
    meal_types = models.ManyToManyField(
        MealType, blank=True, related_name="recipes")
    cooking_methods = models.ManyToManyField(
        CookingMethod, blank=True, related_name="recipes")
    ingredients = models.ManyToManyField(
        "Ingredient",
        through="RecipeIngredient",
        related_name="recipes",
    )

    class Meta:
        ordering = ["-published_at", "title"]

    IMAGE_VARIANT_FIELDS = [
        "image_thumb_avif",
        "image_thumb_webp",
        "image_small_avif",
        "image_small_webp",
        "image_medium_avif",
        "image_medium_webp",
        "image_large_avif",
        "image_large_webp",
    ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        image_changed = False
        servings_changed = False
        if self.pk is None:
            image_changed = bool(self.image)
        else:
            needs_previous = update_fields is None or "image" in update_fields or "servings" in update_fields
            previous = (
                Recipe.objects.filter(pk=self.pk).values("image", "servings").first()
                if needs_previous
                else None
            )

            if update_fields is None or "image" in update_fields:
                previous_image_name = previous.get("image") if previous else None
                current_image_name = getattr(self.image, "name", None) if self.image else None
                image_changed = previous_image_name != current_image_name
            else:
                image_changed = False

            if update_fields is None or "servings" in update_fields:
                previous_servings = previous.get("servings") if previous else None
                servings_changed = previous_servings != self.servings
            else:
                servings_changed = False

        if not self.slug:
            self.slug = _generate_unique_slug(self, self.title)
        if not self.meta_title:
            self.meta_title = self.title
        super().save(*args, **kwargs)
        if image_changed:
            self._generate_image_variants()
        if servings_changed:
            Recipe.objects.filter(pk=self.pk).update(nutrition_dirty=True)

    def __str__(self) -> str:  # pragma: no cover
        return self.title

    def _generate_image_variants(self) -> None:
        if not self.image:
            return
        for field_name in self.IMAGE_VARIANT_FIELDS:
            spec = getattr(self, field_name, None)
            if hasattr(spec, "generate"):
                spec.generate()


class RecipeIngredient(TimeStampedModel):
    """Sujungimas tarp recepto ir ingrediento su kiekiu."""

    recipe = models.ForeignKey(
        Recipe, related_name="recipe_ingredients", on_delete=models.CASCADE)
    ingredient = models.ForeignKey(
        Ingredient, related_name="ingredient_recipes", on_delete=models.PROTECT)
    group = models.ForeignKey(
        IngredientGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recipe_ingredients",
    )
    amount = models.DecimalField(max_digits=7, decimal_places=2)
    unit = models.ForeignKey(MeasurementUnit, on_delete=models.PROTECT)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Recepto ingredientas"
        verbose_name_plural = "Recepto ingredientai"
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                condition=Q(group__isnull=True),
                name="uniq_recipe_ingredient_no_group",
            ),
            models.UniqueConstraint(
                fields=["recipe", "ingredient", "group"],
                condition=Q(group__isnull=False),
                name="uniq_recipe_ingredient_in_group",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.recipe}: {self.amount} {self.unit.short_name} {self.ingredient.name}"


class RecipeStep(TimeStampedModel):
    """Chronologinis žingsnis recepto ruošimui."""

    recipe = models.ForeignKey(
        Recipe, related_name="steps", on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    note = models.TextField(blank=True)
    image = models.ImageField(
        upload_to="recipes/steps/", blank=True, null=True)
    image_thumb_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFill(250, 250)],
        format="AVIF",
        options={"quality": 80},
    )
    image_thumb_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFill(250, 250)],
        format="WEBP",
        options={"quality": 80},
    )
    image_small_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=320)],
        format="AVIF",
        options={"quality": 80},
    )
    image_small_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=320)],
        format="WEBP",
        options={"quality": 80},
    )
    image_medium_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=768)],
        format="AVIF",
        options={"quality": 82},
    )
    image_medium_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=768)],
        format="WEBP",
        options={"quality": 82},
    )
    image_large_avif = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=1280)],
        format="AVIF",
        options={"quality": 85},
    )
    image_large_webp = ImageSpecField(
        source="image",
        processors=[ResizeToFit(width=1280)],
        format="WEBP",
        options={"quality": 85},
    )
    duration = models.PositiveIntegerField(
        null=True, blank=True, help_text="Trukmė minutėmis")
    video_url = models.URLField(blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("recipe", "order")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.recipe.title} – žingsnis {self.order}"

    IMAGE_VARIANT_FIELDS = [
        "image_thumb_avif",
        "image_thumb_webp",
        "image_small_avif",
        "image_small_webp",
        "image_medium_avif",
        "image_medium_webp",
        "image_large_avif",
        "image_large_webp",
    ]

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        image_changed = False
        if self.pk is None:
            image_changed = bool(self.image)
        else:
            if update_fields is not None and "image" not in update_fields:
                image_changed = False
            else:
                previous_image_name = (
                    RecipeStep.objects.filter(pk=self.pk).values_list("image", flat=True).first()
                )
                current_image_name = getattr(self.image, "name", None) if self.image else None
                image_changed = previous_image_name != current_image_name

        super().save(*args, **kwargs)
        if image_changed:
            self._generate_image_variants()

    def _generate_image_variants(self) -> None:
        if not self.image:
            return
        for field_name in self.IMAGE_VARIANT_FIELDS:
            spec = getattr(self, field_name, None)
            if hasattr(spec, "generate"):
                spec.generate()


class Bookmark(TimeStampedModel):
    """Naudotojo išsaugotas receptas."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name="bookmarks")
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="bookmarks")

    class Meta:
        unique_together = ("user", "recipe")
        ordering = ["-created_at"]


class Rating(TimeStampedModel):
    """Naudotojo įvertis (1–5)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name="ratings")
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="ratings")
    value = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Vertinimas 1-5",
    )

    class Meta:
        unique_together = ("user", "recipe")


class Comment(TimeStampedModel):
    """Naudotojo komentaras prie recepto."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name="comments")
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField()
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"Komentaras #{self.pk}"


class RecipeNutritionJobStatus(models.TextChoices):
    QUEUED = "queued", "Eilėje"
    SUBMITTED = "submitted", "Pateikta (batch)"
    RUNNING = "running", "Vykdoma"
    SUCCEEDED = "succeeded", "Pavyko"
    FAILED = "failed", "Nepavyko"


class RecipeNutritionJob(TimeStampedModel):
    """Asinchroninis nutrition informacijos generavimo job'as."""

    recipe = models.ForeignKey(
        Recipe,
        related_name="nutrition_jobs",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=RecipeNutritionJobStatus.choices,
        default=RecipeNutritionJobStatus.QUEUED,
    )
    input_hash = models.CharField(max_length=64)
    openai_batch_id = models.CharField(max_length=100, blank=True, default="")
    openai_batch_submitted_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["recipe", "status", "created_at"]),
        ]

    @staticmethod
    def compute_input_hash(*, servings: int, ingredient_rows: list[tuple]) -> str:
        """Sugeneruoja stabilų SHA256 hash'ą pagal porcijas ir ingredientų eilutes.

        `ingredient_rows` tikimasi kaip list of tuples:
        (ingredient_id, group_id, unit_id, amount, note)
        """

        parts: list[str] = [f"servings={servings}"]
        for ingredient_id, group_id, unit_id, amount, note in ingredient_rows:
            parts.append(
                "|".join(
                    [
                        str(ingredient_id),
                        str(group_id or ""),
                        str(unit_id),
                        str(amount),
                        (note or "").strip(),
                    ]
                )
            )
        raw = "\n".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
