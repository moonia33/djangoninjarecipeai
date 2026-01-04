from __future__ import annotations

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Naktinis SEO meta pipeline: fill_missing_recipe_meta. Skirta cron/systemd timer'iams."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Įtraukti nepublikuotus receptus (perduodama fill komandai).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti planą.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_drafts: bool = options["include_drafts"]
        dry_run: bool = options["dry_run"]

        self.stdout.write("[meta-nightly] fill missing meta...")
        call_command(
            "fill_missing_recipe_meta",
            limit=limit,
            include_drafts=include_drafts,
            dry_run=dry_run,
        )

        self.stdout.write(self.style.SUCCESS("[meta-nightly] done"))
