"""Admino registracijos."""

from django import forms
from django.contrib import admin

from recipes import models


class MarkdownEditorWidget(forms.Textarea):
    class Media:
        css = {
            "all": [
                "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css",
                "https://unpkg.com/easymde/dist/easymde.min.css",
                "recipes/markdown_editor.css",
            ]
        }
        js = [
            "https://unpkg.com/easymde/dist/easymde.min.js",
            "recipes/markdown_editor.js",
        ]

    def __init__(self, attrs=None):
        base_attrs = {
            "data-md-editor": "true",
            "style": "width: 100%;",
            "class": "vLargeTextField",
        }
        attrs = {**base_attrs, **(attrs or {})}
        super().__init__(attrs=attrs)


class RecipeAdminForm(forms.ModelForm):
    """Markdown aprašymas (be CKEditor)."""

    description = forms.CharField(
        label="Pagrindinis aprašymas (Markdown)",
        widget=MarkdownEditorWidget(attrs={"rows": 10}),
        required=False,
        help_text="Markdown (pvz. **bold**, *italic*, sąrašai, antraštės).",
    )

    note = forms.CharField(
        label="Pastaba / tip (paprastas tekstas)",
        widget=forms.Textarea(attrs={"rows": 3, "style": "width: 100%;"}),
        required=False,
        help_text="Trumpa pastaba (nebūtina).",
    )

    class Meta:
        model = models.Recipe
        fields = "__all__"


class RecipeStepInlineForm(forms.ModelForm):
    description = forms.CharField(
        label="Žingsnio aprašymas (Markdown)",
        widget=MarkdownEditorWidget(attrs={"rows": 6}),
        required=False,
        help_text="Markdown. Jei žingsnis neturi teksto (tik vaizdas/video) – gali būti tuščias.",
    )

    note = forms.CharField(
        label="Žingsnio pastaba / tip (paprastas tekstas)",
        widget=forms.Textarea(attrs={"rows": 2, "style": "width: 100%;"}),
        required=False,
        help_text="Nebūtina – naudok kaip trumpą tip'ą ar pastabą.",
    )

    class Meta:
        model = models.RecipeStep
        fields = "__all__"


class RecipeIngredientInline(admin.TabularInline):
    """Greitas ingredientų redagavimas receptų formoje."""

    model = models.RecipeIngredient
    extra = 0


class RecipeStepInline(admin.StackedInline):
    """Žingsnių redagavimas admino sąsajoje."""

    model = models.RecipeStep
    form = RecipeStepInlineForm
    extra = 0
    ordering = ("order",)
    fieldsets = (
        ("Bazinė informacija", {"fields": ("order", "title", "duration")}),
        (
            "Turinys",
            {"fields": ("description", "note", "image", "video_url")},
        ),
    )


@admin.register(models.Recipe)
class RecipeAdmin(admin.ModelAdmin):
    form = RecipeAdminForm
    list_display = ("title", "difficulty", "published_at", "updated_at")
    list_filter = ("difficulty", "published_at", "meal_types", "cuisines")
    search_fields = ("title", "description", "meta_description")
    autocomplete_fields = ("categories", "tags", "cuisines",
                           "meal_types", "cooking_methods")
    inlines = [RecipeIngredientInline, RecipeStepInline]
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)


@admin.register(models.IngredientCategory)
class IngredientCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)


@admin.register(models.RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent")
    search_fields = ("name",)


@admin.register(models.MeasurementUnit)
class MeasurementUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "unit_type")
    list_filter = ("unit_type",)


@admin.register(models.MealType, models.Cuisine, models.CookingMethod, models.Tag)
class SimpleLookupAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(models.RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "group", "amount", "unit")
    search_fields = ("recipe__title", "ingredient__name")


@admin.register(models.IngredientGroup)
class IngredientGroupAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(models.RecipeStep)
class RecipeStepAdmin(admin.ModelAdmin):
    list_display = ("recipe", "order", "title")
    ordering = ("recipe", "order")


@admin.register(models.Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe", "created_at")
    search_fields = ("user__email", "recipe__title")


@admin.register(models.Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe", "value")
    search_fields = ("user__email", "recipe__title")


@admin.register(models.Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("recipe", "user", "is_approved", "created_at")
    list_filter = ("is_approved",)
    search_fields = ("content", "user__email", "recipe__title")
    actions = ["approve_comments"]

    @admin.action(description="Pažymėti kaip patvirtintus")
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
