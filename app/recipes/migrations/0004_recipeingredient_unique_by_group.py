from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0003_ingredientgroup_recipeingredient_group"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="recipeingredient",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="recipeingredient",
            constraint=models.UniqueConstraint(
                fields=("recipe", "ingredient"),
                condition=Q(group__isnull=True),
                name="uniq_recipe_ingredient_no_group",
            ),
        ),
        migrations.AddConstraint(
            model_name="recipeingredient",
            constraint=models.UniqueConstraint(
                fields=("recipe", "ingredient", "group"),
                condition=Q(group__isnull=False),
                name="uniq_recipe_ingredient_in_group",
            ),
        ),
    ]
