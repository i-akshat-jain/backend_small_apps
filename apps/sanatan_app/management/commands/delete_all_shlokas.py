"""
Django management command to delete all shlokas and their related data.
This will delete:
- All ShlokaExplanation records
- All ReadingLog records
- All ShlokaReadStatus records
- All Favorite records
- All Shloka records

Run: python manage.py delete_all_shlokas
"""
from django.core.management.base import BaseCommand
from apps.sanatan_app.models import Shloka, ShlokaExplanation, ReadingLog, ShlokaReadStatus, Favorite


class Command(BaseCommand):
    help = 'Delete all shlokas and their related data (explanations, reading logs, read status, favorites)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion (required to actually delete)',
        )

    def handle(self, *args, **options):
        """Delete all shlokas and related data."""
        confirm = options['confirm']
        
        if not confirm:
            self.stdout.write(self.style.WARNING(
                "This will delete ALL shlokas and related data!\n"
                "Run with --confirm to proceed."
            ))
            return
        
        # Count records before deletion
        shloka_count = Shloka.objects.count()
        explanation_count = ShlokaExplanation.objects.count()
        reading_log_count = ReadingLog.objects.count()
        read_status_count = ShlokaReadStatus.objects.count()
        favorite_count = Favorite.objects.count()
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("DELETING ALL SHLOKAS AND RELATED DATA"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"\nCurrent counts:")
        self.stdout.write(f"  - Shlokas: {shloka_count}")
        self.stdout.write(f"  - Explanations: {explanation_count}")
        self.stdout.write(f"  - Reading Logs: {reading_log_count}")
        self.stdout.write(f"  - Read Status: {read_status_count}")
        self.stdout.write(f"  - Favorites: {favorite_count}")
        self.stdout.write("\nDeleting...")
        
        # Delete all shlokas (CASCADE will handle related records)
        deleted_count, _ = Shloka.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully deleted {deleted_count} records"))
        self.stdout.write(self.style.SUCCESS("All shlokas and related data have been deleted."))
        self.stdout.write("\nYou can now regenerate shlokas from scratch using:")
        self.stdout.write("  python manage.py ensure_shloka_explanations --check-format")


