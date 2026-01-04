from __future__ import annotations

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = (
        "Naktinis nutrition pipeline: enqueue_recipe_nutrition_jobs + submit_recipe_nutrition_batch. "
        "Skirta cron/systemd timer'iams."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--include-drafts",
            action="store_true",
            help="Įtraukti nepublikuotus receptus (perduodama enqueue komandai).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Kurti job'us net jei nutrition_dirty=false (perduodama enqueue komandai).",
        )
        parser.add_argument(
            "--completion-window",
            type=str,
            default="24h",
            help="OpenAI batch completion window (pvz. 24h).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB / nesiųsti į OpenAI, tik parodyti planą.",
        )

    def handle(self, *args, **options):
        limit: int = options["limit"]
        include_drafts: bool = options["include_drafts"]
        force: bool = options["force"]
        completion_window: str = options["completion_window"]
        dry_run: bool = options["dry_run"]

        self.stdout.write("[nutrition-nightly] enqueue...")
        call_command(
            "enqueue_recipe_nutrition_jobs",
            limit=limit,
            include_drafts=include_drafts,
            force=force,
            dry_run=dry_run,
        )

        self.stdout.write("[nutrition-nightly] submit batch...")
        call_command(
            "submit_recipe_nutrition_batch",
            limit=limit,
            completion_window=completion_window,
            dry_run=dry_run,
        )

        self.stdout.write(self.style.SUCCESS("[nutrition-nightly] done"))
