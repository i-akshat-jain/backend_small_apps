"""
Django management command to extract shlokas from PDF books.
Run: python manage.py extract_shlokas_from_pdfs --num-shlokas 20
"""
from django.core.management.base import BaseCommand
from apps.sanatan_app.services.shloka_service import ShlokaService


class Command(BaseCommand):
    help = 'Extract shlokas from PDF books using AI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-shlokas',
            type=int,
            default=20,
            help='Number of shlokas to extract (default: 20)',
        )

    def handle(self, *args, **options):
        """Extract shlokas from PDFs."""
        num_shlokas = options['num_shlokas']
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Extracting shlokas from PDFs"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"\nExtracting {num_shlokas} shlokas...")
        
        # Initialize service
        shloka_service = ShlokaService()
        
        # Extract shlokas
        try:
            shloka_service._extract_new_shlokas_from_pdfs(user=None, num_shlokas=num_shlokas)
            
            # Count how many were actually added
            from apps.sanatan_app.models import Shloka
            total_count = Shloka.objects.count()
            
            self.stdout.write(self.style.SUCCESS(f"\n✓ Extraction complete!"))
            self.stdout.write(f"Total shlokas in database: {total_count}")
            self.stdout.write("\nNext step: Generate explanations with:")
            self.stdout.write("  python manage.py ensure_shloka_explanations --check-format")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error extracting shlokas: {str(e)}"))
            raise


