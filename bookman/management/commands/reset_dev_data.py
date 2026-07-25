from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandError

FIXTURE_PATHS = [
    "bookman/fixtures/m_municipality-data.json",
    "bookman/fixtures/m_branch-data.json",
    "bookman/fixtures/m_category-data.json",
    "bookman/fixtures/author-data.json",
    "bookman/fixtures/book-data.json",
    "bookman/fixtures/branch-book-stock-data.json",
    "bookman/fixtures/customer-data.json",
    "bookman/fixtures/library-staff-data.json",
    "bookman/fixtures/branch-closed-day-data.json",
    "bookman/fixtures/lending-data.json",
    "bookman/fixtures/reservation-data.json",
    "bookman/fixtures/search-condition-data.json",
]


class Command(BaseCommand):
    help = "開発用DBをflushし、Bookmanの初期fixtureを順番に投入します。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="DEBUG=False でも実行します。共有DBや本番DBでは使わないでください。",
        )

    def handle(self, *args, **options):
        verbosity = options["verbosity"]
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "reset_dev_data は DEBUG=True の開発環境だけで実行できます。"
                "必要な場合だけ --force を付けてください。"
            )

        if verbosity > 0:
            self.stdout.write("Flushing database...")
        call_command("flush", interactive=False, verbosity=0)

        if verbosity > 0:
            self.stdout.write("Loading Bookman fixtures...")
        call_command("loaddata", *FIXTURE_PATHS, verbosity=verbosity)

        if verbosity > 0:
            self.stdout.write(self.style.SUCCESS("Development data reset complete."))
