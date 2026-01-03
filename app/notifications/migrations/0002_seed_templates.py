from django.db import migrations


def seed_templates(apps, schema_editor):  # pragma: no cover - duomenų migracija
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    templates = [
        {
            "key": "welcome",
            "name": "Sveikinimo laiškas",
            "description": "Išsiunčiama po registracijos ar administratoriaus sukūrimo.",
            "subject": "Sveiki atvykę į Apetitą, {{ user_name }}!",
            "body_text": (
                "Sveiki, {{ user_name }}!\n\n"
                "Džiaugiamės, kad prisijungėte prie Apetito. Prisijunkite prie paskyros ir pradėkite kurti receptus.\n"
                "Jei šis laiškas jus pasiekė netyčia, ignoruokite jį."
            ),
            "body_html": (
                "<p>Sveiki, <strong>{{ user_name }}</strong>!</p>"
                "<p>Džiaugiamės, kad prisijungėte prie Apetito. Prisijunkite prie paskyros ir pradėkite kurti receptus.</p>"
                "<p>Jei šis laiškas jus pasiekė netyčia, tiesiog ignoruokite.</p>"
            ),
        },
        {
            "key": "password_reset",
            "name": "Slaptažodžio atstatymas",
            "description": "Standartinis laiškas su laikina nuoroda.",
            "subject": "Slaptažodžio atkūrimas Apetite",
            "body_text": (
                "Sveiki, {{ user_name }}!\n\nNorėdami atstatyti slaptažodį, spauskite nuorodą: {{ reset_url }}\n"
                "Nuoroda galios {{ valid_minutes }} min.\nJei užklausos nesiuntėte, ignoruokite."
            ),
            "body_html": (
                "<p>Sveiki, <strong>{{ user_name }}</strong>!</p>"
                "<p>Norėdami atstatyti slaptažodį, spauskite nuorodą: <a href=\"{{ reset_url }}\">Atstatyti slaptažodį</a>.</p>"
                "<p>Nuoroda galios {{ valid_minutes }} min. Jei užklausos nesiuntėte, ignoruokite laišką.</p>"
            ),
        },
        {
            "key": "recipe_review",
            "name": "Recepto peržiūra",
            "description": "Informuojama apie pateiktą receptą, kai laukia patvirtinimo.",
            "subject": "Jūsų receptas '{{ recipe_title }}' laukia patvirtinimo",
            "body_text": (
                "Sveiki, {{ user_name }}!\n\n"
                "Gavome receptą '{{ recipe_title }}'. Redaktoriai jį peržiūrės, o rezultatą pranešime el. paštu.\n"
                "Ačiū, kad kuriate turinį Apetite!"
            ),
            "body_html": (
                "<p>Sveiki, <strong>{{ user_name }}</strong>!</p>"
                "<p>Gavome receptą <em>{{ recipe_title }}</em>. Mūsų komanda jį peržiūrės ir apie rezultatus pranešime atskiru laišku.</p>"
                "<p>Ačiū, kad kuriate turinį Apetite!</p>"
            ),
        },
    ]

    for template_data in templates:
        defaults = template_data.copy()
        key = defaults.pop("key")
        EmailTemplate.objects.update_or_create(key=key, defaults=defaults)


def unseed_templates(apps, schema_editor):  # pragma: no cover - duomenų migracija
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    EmailTemplate.objects.filter(
        key__in=["welcome", "password_reset", "recipe_review"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
