from django.db import migrations


COMMENT_TEMPLATE = {
    "key": "comment_notification",
    "name": "Naujas komentaras administratoriui",
    "description": "Perspėja administratorių apie naujai pateiktą komentarą.",
    "subject": "Naujas komentaro pateikimas receptui '{{ recipe_title }}'",
    "body_text": (
        "Sveiki,\n\n"
        "Naujas komentaras pateiktas prie recepto '{{ recipe_title }}'.\n"
        "Autorius: {{ author_name }}\n"
        "Turinys:\n{{ content }}\n\n"
        "Peržiūrėkite: {{ admin_url }}"
    ),
    "body_html": (
        "<p>Sveiki,</p>"
        "<p>Gautas naujas komentaras prie recepto <strong>{{ recipe_title }}</strong>.</p>"
        "<ul>"
        "<li><strong>Autorius:</strong> {{ author_name }}</li>"
        "<li><strong>Pateikta:</strong> {{ created_at }}</li>"
        "</ul>"
        "<p>{{ content|linebreaksbr }}</p>"
        "<p><a href=\"{{ admin_url }}\">Atverti komentaro formą</a></p>"
    ),
}


def add_comment_template(apps, schema_editor):  # pragma: no cover - duomenų migracija
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    defaults = COMMENT_TEMPLATE.copy()
    key = defaults.pop("key")
    EmailTemplate.objects.update_or_create(key=key, defaults=defaults)


def remove_comment_template(apps, schema_editor):  # pragma: no cover - duomenų migracija
    EmailTemplate = apps.get_model("notifications", "EmailTemplate")
    EmailTemplate.objects.filter(key=COMMENT_TEMPLATE["key"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_seed_templates"),
    ]

    operations = [
        migrations.RunPython(add_comment_template, remove_comment_template),
    ]
