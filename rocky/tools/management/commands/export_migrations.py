from pathlib import Path
from typing import Any

import structlog
from django.core.management import BaseCommand, CommandParser
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Export migrations to SQL"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("app", action="store", type=str, help="Django app")
        parser.add_argument("from_id", action="store", type=int, help="Migration id to start from")
        parser.add_argument("--output-folder", action="store", default="export_migrations", help="Output folder")

    def handle(self, **options: Any) -> None:
        # Get the database we're operating from
        connection = connections[DEFAULT_DB_ALIAS]

        # Load up a loader to get all the migration data, but don't replace migrations
        loader = MigrationLoader(connection, replace_migrations=False)

        # Create output folder
        output_folder = Path(options["output_folder"])
        output_folder.mkdir(parents=True, exist_ok=True)

        # Find migration record to start from
        migration_match = MigrationRecorder.Migration.objects.get(
            app=options["app"], name__istartswith=f"{options['from_id']:04d}"
        )

        migrations_to_export = MigrationRecorder.Migration.objects.filter(
            id__gte=migration_match.id, app=options["app"]
        )

        for migration in migrations_to_export:
            logger.info("Exporting %s", migration.id)

            # Generate SQL
            target = (migration.app, migration.name)
            plan = [(loader.graph.nodes[target], False)]
            sql_statements = loader.collect_sql(plan)

            # Write SQL to file
            output_file = output_folder / f"{migration.id:04d}.{migration.app}.{migration.name}.sql"
            output_file.write_text("\n".join(sql_statements))
