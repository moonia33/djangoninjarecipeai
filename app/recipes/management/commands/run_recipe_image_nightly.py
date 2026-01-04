from __future__ import annotations

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Naktinis hero paveikslo pipeline: enqueue_recipe_image_jobs + process_recipe_image_jobs. Skirta cron/systemd." 

    def add_arguments(self, parser):
        parser.add_argument("--enqueue-limit", type=int, default=200)
        parser.add_argument("--process-limit", type=int, default=20)
        parser.add_argument(
            "--include-non-generated",
            action="store_true",
            help="Įtraukti ir ne AI receptus (perduodama enqueue komandai).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nieko nekeisti DB, tik parodyti planą (enqueue dry-run).",
        )

    def handle(self, *args, **options):
        enqueue_limit: int = options["enqueue_limit"]
        process_limit: int = options["process_limit"]
        include_non_generated: bool = options["include_non_generated"]
        dry_run: bool = options["dry_run"]

        self.stdout.write("[image-nightly] enqueue...")
        call_command(
            "enqueue_recipe_image_jobs",
            limit=enqueue_limit,
            include_non_generated=include_non_generated,
            dry_run=dry_run,
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("[image-nightly] done (dry-run)"))
            return

        self.stdout.write("[image-nightly] process...")
        call_command(
            "process_recipe_image_jobs",
            limit=process_limit,
        )

        self.stdout.write(self.style.SUCCESS("[image-nightly] done"))
