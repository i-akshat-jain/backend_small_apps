"""
Django management command to systematically extract and save shlokas from PDF books.

This command reads shlokas from the PDF books chapter by chapter, extracts them using AI,
validates the data, and saves them to the database in a consistent pattern.

Run: python manage.py save_shlokas_from_books --chapters 1-18 --book-name "Bhagavad Gita"
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.sanatan_app.models import Shloka
from apps.sanatan_app.services.shloka_service import ShlokaService
from apps.sanatan_app.services.book_context_service import BookContextService
import logging
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Systematically extract and save shlokas from PDF books to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chapters',
            type=str,
            default='1-18',
            help='Chapter range to process (e.g., "1-18" or "1,2,3" or "1-5,10-12")',
        )
        parser.add_argument(
            '--book-name',
            type=str,
            default='Bhagavad Gita',
            help='Name of the book (default: "Bhagavad Gita")',
        )
        parser.add_argument(
            '--max-shlokas-per-chapter',
            type=int,
            default=None,
            help='Maximum number of shlokas to extract per chapter (default: extract all found)',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip shlokas that already exist in the database',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving to database (for testing)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed debugging information',
        )
        parser.add_argument(
            '--skip-explanations',
            action='store_true',
            help='Skip generating explanations (only extract shlokas)',
        )
        parser.add_argument(
            '--create-explanations-for-existing',
            action='store_true',
            help='Create explanations for existing shlokas that don\'t have them',
        )

    def handle(self, *args, **options):
        """Extract and save shlokas from PDF books."""
        chapters = self._parse_chapters(options['chapters'])
        book_name = options['book_name']
        max_per_chapter = options['max_shlokas_per_chapter']
        skip_existing = options['skip_existing']
        dry_run = options['dry_run']
        verbose = options['verbose']
        skip_explanations = options['skip_explanations']
        create_explanations_for_existing = options.get('create_explanations_for_existing', False)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Extracting Shlokas from PDF Books"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"\nBook: {book_name}")
        self.stdout.write(f"Chapters: {chapters}")
        self.stdout.write(f"Max per chapter: {max_per_chapter or 'All'}")
        self.stdout.write(f"Skip existing: {skip_existing}")
        self.stdout.write(f"Dry run: {dry_run}")
        self.stdout.write(f"Generate explanations: {not skip_explanations}")
        self.stdout.write("")

        # Initialize services
        shloka_service = ShlokaService()
        book_context_service = BookContextService()

        # Check if PDFs exist and show paths
        self.stdout.write(f"\nChecking PDF files...")
        self.stdout.write(f"  English PDF path: {book_context_service.english_book_path}")
        self.stdout.write(f"  English PDF exists: {book_context_service.english_book_path.exists()}")
        self.stdout.write(f"  Hindi PDF path: {book_context_service.hindi_book_path}")
        self.stdout.write(f"  Hindi PDF exists: {book_context_service.hindi_book_path.exists()}")
        self.stdout.write("")

        if not book_context_service.english_book_path.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"✗ English PDF not found: {book_context_service.english_book_path}"
                )
            )
            self.stdout.write(
                self.style.ERROR(
                    f"  Please ensure the PDF file exists at this location."
                )
            )
            return

        # Get existing shlokas for duplicate checking
        existing_shlokas = set()
        if skip_existing:
            existing_shlokas = set(
                Shloka.objects.filter(book_name=book_name).values_list(
                    'chapter_number', 'verse_number'
                )
            )
            self.stdout.write(
                f"Found {len(existing_shlokas)} existing shlokas in database"
            )
            self.stdout.write("")

        # Statistics
        total_added = 0
        total_skipped = 0
        total_errors = 0
        chapter_stats = {}

        # Process each chapter
        for chapter_num in chapters:
            self.stdout.write("-" * 70)
            self.stdout.write(
                self.style.WARNING(f"Processing Chapter {chapter_num}...")
            )
            self.stdout.write("-" * 70)

            try:
                added, skipped, errors = self._process_chapter(
                    shloka_service=shloka_service,
                    book_context_service=book_context_service,
                    book_name=book_name,
                    chapter_num=chapter_num,
                    max_shlokas=max_per_chapter,
                    existing_shlokas=existing_shlokas,
                    skip_existing=skip_existing,
                    dry_run=dry_run,
                    verbose=verbose,
                    skip_explanations=skip_explanations,
                    create_explanations_for_existing=create_explanations_for_existing,
                )

                chapter_stats[chapter_num] = {
                    'added': added,
                    'skipped': skipped,
                    'errors': errors,
                }

                total_added += added
                total_skipped += skipped
                total_errors += errors

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Chapter {chapter_num}: Added {added}, "
                        f"Skipped {skipped}, Errors {errors}"
                    )
                )
                self.stdout.write("")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Error processing Chapter {chapter_num}: {str(e)}"
                    )
                )
                logger.exception(e)
                total_errors += 1
                self.stdout.write("")

        # Final summary
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Extraction Summary"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Total chapters processed: {len(chapters)}")
        self.stdout.write(
            self.style.SUCCESS(f"Total shlokas added: {total_added}")
        )
        self.stdout.write(
            self.style.WARNING(f"Total shlokas skipped: {total_skipped}")
        )
        self.stdout.write(
            self.style.ERROR(f"Total errors: {total_errors}")
        )

        if not dry_run:
            total_in_db = Shloka.objects.filter(book_name=book_name).count()
            self.stdout.write(f"\nTotal shlokas in database for '{book_name}': {total_in_db}")
        else:
            self.stdout.write(
                self.style.WARNING("\n⚠ DRY RUN - No data was saved to database")
            )

        self.stdout.write("")

    def _parse_chapters(self, chapters_str):
        """Parse chapter string into list of chapter numbers."""
        chapters = set()

        # Handle ranges like "1-18" or "1-5,10-12"
        parts = chapters_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-18"
                start, end = part.split('-')
                try:
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    chapters.update(range(start_num, end_num + 1))
                except ValueError:
                    self.stdout.write(
                        self.style.ERROR(f"Invalid range: {part}")
                    )
            else:
                # Single number
                try:
                    chapters.add(int(part.strip()))
                except ValueError:
                    self.stdout.write(
                        self.style.ERROR(f"Invalid chapter number: {part}")
                    )

        return sorted(list(chapters))

    def _process_chapter(
        self,
        shloka_service,
        book_context_service,
        book_name,
        chapter_num,
        max_shlokas,
        existing_shlokas,
        skip_existing,
        dry_run,
        verbose=False,
        skip_explanations=False,
        create_explanations_for_existing=False,
    ):
        """Process a single chapter and extract shlokas."""
        added = 0
        skipped = 0
        errors = 0

        # Load PDF
        self.stdout.write(f"  Loading PDF: {book_context_service.english_book_path.name}")
        pdf_reader = book_context_service._load_pdf(
            book_context_service.english_book_path
        )
        if not pdf_reader:
            self.stdout.write(
                self.style.ERROR("  ✗ Failed to load PDF")
            )
            return added, skipped, errors + 1

        total_pages = len(pdf_reader.pages)
        self.stdout.write(f"  ✓ PDF loaded successfully ({total_pages} total pages)")

        # Find chapter start page
        self.stdout.write(f"  Searching for Chapter {chapter_num}...")
        chapter_start_page = self._find_chapter_start_page(
            pdf_reader, chapter_num
        )

        if chapter_start_page is None:
            # Fallback to estimated page
            chapter_start_page = (chapter_num - 1) * 15
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ Could not find Chapter {chapter_num} start page, "
                    f"using estimated page {chapter_start_page}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Found Chapter {chapter_num} starting at page {chapter_start_page}"
                )
            )

        # Extract chapter text
        start_page = chapter_start_page
        end_page = min(chapter_start_page + 25, total_pages)

        self.stdout.write(
            f"  Extracting text from pages {start_page}-{end_page}..."
        )

        raw_chapter_text = book_context_service._extract_text_from_pdf(
            pdf_reader, (start_page, end_page)
        )

        if not raw_chapter_text:
            self.stdout.write(
                self.style.ERROR("  ✗ No text extracted from chapter")
            )
            # Try to extract from a single page to debug
            if start_page < total_pages:
                test_text = book_context_service._extract_text_from_pdf(
                    pdf_reader, (start_page, start_page + 1)
                )
                if test_text:
                    self.stdout.write(
                        f"  Debug: Extracted {len(test_text)} chars from single page {start_page}"
                    )
                    self.stdout.write(f"  Sample (first 200 chars): {test_text[:200]}")
            return added, skipped, errors + 1

        self.stdout.write(
            f"  ✓ Extracted {len(raw_chapter_text)} characters of raw text"
        )

        # Clean the text
        chapter_text = shloka_service._clean_pdf_text(raw_chapter_text)
        self.stdout.write(
            f"  ✓ After cleaning: {len(chapter_text)} characters"
        )

        # Show sample of extracted text for debugging
        sample_length = min(500, len(chapter_text))
        if sample_length > 0:
            sample_text = chapter_text[:sample_length]
            self.stdout.write(f"  Sample text (first {sample_length} chars):")
            self.stdout.write(f"  {sample_text}")
            self.stdout.write("")

        # Validate that we have shloka content
        has_devanagari = any(
            0x0900 <= ord(c) <= 0x097F for c in chapter_text
        )
        has_verse = 'VERSE' in chapter_text or 'verse' in chapter_text.lower()
        has_chapter = f'Chapter {chapter_num}' in chapter_text or f'CHAPTER {chapter_num}' in chapter_text
        
        # Check if we got the wrong chapter (e.g., looking for Chapter 1 but got Chapter 13)
        # Look at the FIRST 500 characters to see what chapter actually starts the content
        wrong_chapter = False
        text_start = chapter_text[:500]  # Check first 500 chars - this is where chapter markers appear
        
        # Find the first chapter marker in the START of the text
        first_chapter_found = None
        first_chapter_pos = len(text_start)
        
        for check_chapter in range(1, 19):
            for pattern in [f'Chapter {check_chapter}', f'CHAPTER {check_chapter}']:
                pos = text_start.find(pattern)
                if pos != -1 and pos < first_chapter_pos:
                    first_chapter_pos = pos
                    first_chapter_found = check_chapter
        
        # Check if our target chapter appears in the first 500 chars
        target_chapter_in_start = False
        for pattern in [f'Chapter {chapter_num}', f'CHAPTER {chapter_num}']:
            if pattern in text_start:
                target_chapter_in_start = True
                break
        
        # If the first chapter found is not our target chapter, we have wrong chapter
        # This is strict: if "Chapter 13" appears first and "Chapter 1" doesn't appear in first 500 chars, it's wrong
        if first_chapter_found is not None and first_chapter_found != chapter_num:
            if not target_chapter_in_start:
                wrong_chapter = True
                self.stdout.write(
                    self.style.WARNING(
                        f"    ⚠ Text starts with Chapter {first_chapter_found} (looking for Chapter {chapter_num})"
                    )
                )
                self.stdout.write(
                    f"    First chapter marker found at position {first_chapter_pos} in text start"
                )
                self.stdout.write(
                    f"    Chapter {chapter_num} not found in first 500 characters"
                )
        
        # Check for TOC indicators (if we still got TOC, skip it)
        has_toc_indicators = any(
            indicator in chapter_text for indicator in [
                'Contents', 'CONTENTS', 'Table of Contents', 'Preface', 'Introduction'
            ]
        ) and len(chapter_text) < 5000  # TOC is usually shorter

        self.stdout.write(f"  Content analysis:")
        self.stdout.write(f"    - Has Devanagari: {has_devanagari}")
        self.stdout.write(f"    - Has 'VERSE' marker: {has_verse}")
        self.stdout.write(f"    - Has Chapter {chapter_num} marker: {has_chapter}")
        self.stdout.write(f"    - Wrong chapter detected: {wrong_chapter}")
        self.stdout.write(f"    - Looks like TOC: {has_toc_indicators}")
        self.stdout.write("")
        
        # If we detected wrong chapter, try to find correct one
        if wrong_chapter:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ Wrong chapter detected. Searching for correct Chapter {chapter_num}..."
                )
            )
            # Try searching a few pages forward/backward
            for offset in range(-5, 10):
                try_page = start_page + offset
                if try_page < 0 or try_page >= total_pages:
                    continue
                
                test_text = book_context_service._extract_text_from_pdf(
                    pdf_reader, (try_page, min(try_page + 10, total_pages))
                )
                if test_text:
                    test_cleaned = shloka_service._clean_pdf_text(test_text)
                    # Check if this page has the correct chapter
                    has_correct_chapter = (
                        f'Chapter {chapter_num}' in test_cleaned or 
                        f'CHAPTER {chapter_num}' in test_cleaned
                    )
                    # Check if it doesn't have other chapters prominently
                    has_other_chapter = False
                    for other_chapter in range(1, 19):
                        if other_chapter != chapter_num:
                            if f'Chapter {other_chapter}' in test_cleaned or f'CHAPTER {other_chapter}' in test_cleaned:
                                other_pos = test_cleaned.find(f'Chapter {other_chapter}')
                                if other_pos == -1:
                                    other_pos = test_cleaned.find(f'CHAPTER {other_chapter}')
                                correct_pos = test_cleaned.find(f'Chapter {chapter_num}')
                                if correct_pos == -1:
                                    correct_pos = test_cleaned.find(f'CHAPTER {chapter_num}')
                                
                                if other_pos != -1 and (correct_pos == -1 or other_pos < correct_pos):
                                    has_other_chapter = True
                                    break
                    
                    if has_correct_chapter and not has_other_chapter:
                        test_has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in test_cleaned)
                        test_has_verse = 'VERSE' in test_cleaned or 'verse' in test_cleaned.lower()
                        if test_has_devanagari or test_has_verse:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ Found correct Chapter {chapter_num} starting at page {try_page}"
                                )
                            )
                            # Re-extract from the correct page
                            chapter_text = test_cleaned
                            start_page = try_page
                            end_page = min(try_page + 25, total_pages)
                            has_devanagari = test_has_devanagari
                            has_verse = test_has_verse
                            has_chapter = True
                            wrong_chapter = False
                            break

        # If it looks like TOC, warn and try to find better page
        if has_toc_indicators:
            self.stdout.write(
                self.style.WARNING(
                    "  ⚠ Extracted text appears to be from Table of Contents, not actual chapter content"
                )
            )
            self.stdout.write(
                "  Trying to find actual chapter content..."
            )
            # Try searching for a page with actual content
            for offset in range(1, 10):
                try_page = start_page + offset
                if try_page >= total_pages:
                    break
                test_text = book_context_service._extract_text_from_pdf(
                    pdf_reader, (try_page, min(try_page + 5, total_pages))
                )
                if test_text:
                    test_cleaned = shloka_service._clean_pdf_text(test_text)
                    test_has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in test_cleaned)
                    test_has_verse = 'VERSE' in test_cleaned or 'verse' in test_cleaned.lower()
                    if test_has_devanagari or test_has_verse:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Found actual content starting at page {try_page}"
                            )
                        )
                        # Re-extract from the better page
                        chapter_text = test_cleaned
                        start_page = try_page
                        end_page = min(try_page + 25, total_pages)
                        has_devanagari = test_has_devanagari
                        has_verse = test_has_verse
                        break
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "  ✗ Could not find actual chapter content. Please check the PDF manually."
                    )
                )
                return added, skipped, errors

        # If we still have wrong chapter after trying to fix, skip
        if wrong_chapter:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ Could not find correct Chapter {chapter_num} content. Skipping."
                )
            )
            self.stdout.write(
                "  The extracted text appears to be from a different chapter."
            )
            self.stdout.write(
                "  Please check the PDF manually to find the correct page for this chapter."
            )
            return added, skipped, errors
        
        if not has_devanagari and not has_verse:
            self.stdout.write(
                self.style.WARNING(
                    "  ⚠ Chapter text doesn't appear to contain shloka content"
                )
            )
            self.stdout.write(
                "  This might mean the PDF pages don't contain the expected content."
            )
            self.stdout.write(
                "  Try checking if the chapter starts at a different page number."
            )
            return added, skipped, errors

        # Extract shlokas using AI
        shlokas_to_extract = max_shlokas or 50  # Default to 50 if not specified
        self.stdout.write(
            f"  Using AI to extract up to {shlokas_to_extract} shlokas..."
        )
        self.stdout.write(
            f"  Sending {len(chapter_text)} characters to AI..."
        )

        try:
            # Temporarily set logging level to capture AI response details
            import logging as log_module
            original_level = logger.level
            if verbose:
                logger.setLevel(log_module.DEBUG)
            
            shlokas_data = shloka_service._extract_shlokas_with_ai(
                chapter_text, chapter_num, shlokas_to_extract
            )
            
            # Restore logging level
            if verbose:
                logger.setLevel(original_level)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  ✗ Error calling AI: {str(e)}")
            )
            if verbose:
                import traceback
                self.stdout.write(f"  Full traceback:")
                self.stdout.write(traceback.format_exc())
            logger.exception(e)
            return added, skipped, errors + 1

        if not shlokas_data:
            self.stdout.write(
                self.style.WARNING("  ⚠ No shlokas extracted from chapter")
            )
            self.stdout.write(
                "  This could mean:"
            )
            self.stdout.write(
                "    1. The AI couldn't find shlokas in the extracted text"
            )
            self.stdout.write(
                "    2. The text format doesn't match expected shloka format"
            )
            self.stdout.write(
                "    3. The AI returned an empty response or invalid JSON"
            )
            self.stdout.write(
                "    4. Check Django logs for detailed AI response information"
            )
            if verbose:
                self.stdout.write(
                    "  Tip: Check the sample text above to see if it contains shlokas"
                )
                self.stdout.write(
                    "  Tip: The PDF might need different page ranges or chapter detection"
                )
                self.stdout.write(
                    "  Tip: Check logs with: tail -f logs/django.log (or your log file)"
                )
            return added, skipped, errors

        self.stdout.write(
            f"  ✓ AI extracted {len(shlokas_data)} shlokas from chapter"
        )

        # Save shlokas to database
        self.stdout.write("  Saving shlokas to database...")

        for idx, shloka_data in enumerate(shlokas_data, 1):
            try:
                # Extract and validate data types to match model exactly
                # Model: chapter_number = IntegerField, verse_number = IntegerField
                chapter_num_extracted = shloka_data.get('chapter_number')
                verse_num = shloka_data.get('verse_number')
                
                # Ensure integers (handle string numbers from AI)
                try:
                    if chapter_num_extracted is not None:
                        chapter_num_extracted = int(chapter_num_extracted)
                    if verse_num is not None:
                        verse_num = int(verse_num)
                except (ValueError, TypeError):
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Invalid chapter/verse number format"
                        )
                    )
                    skipped += 1
                    continue
                
                # Model: sanskrit_text = TextField (required)
                raw_sanskrit = shloka_data.get('sanskrit_text', '')
                # Model: transliteration = TextField(blank=True, null=True) (optional)
                raw_transliteration = shloka_data.get('transliteration', '')

                # Validate chapter number matches
                if chapter_num_extracted != chapter_num:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter mismatch "
                            f"(expected {chapter_num}, got {chapter_num_extracted})"
                        )
                    )
                    # Use the chapter number we're processing
                    chapter_num_extracted = chapter_num

                # Check if already exists
                if skip_existing and (chapter_num_extracted, verse_num) in existing_shlokas:
                    skipped += 1
                    self.stdout.write(
                        f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                        f"Verse {verse_num} - Already exists, skipping"
                    )
                    continue

                # Clean the text
                cleaned_sanskrit = (
                    shloka_service._clean_pdf_text(raw_sanskrit)
                    if raw_sanskrit
                    else ''
                )
                cleaned_transliteration = (
                    shloka_service._clean_pdf_text(raw_transliteration)
                    if raw_transliteration
                    else ''
                )

                # Validate Sanskrit text
                has_devanagari = (
                    any(0x0900 <= ord(c) <= 0x097F for c in cleaned_sanskrit)
                    if cleaned_sanskrit
                    else False
                )
                has_corrupted = (
                    any(0xE000 <= ord(c) <= 0xF8FF for c in cleaned_sanskrit)
                    if cleaned_sanskrit
                    else False
                )

                if has_corrupted:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - SKIPPED (has corrupted characters)"
                        )
                    )
                    skipped += 1
                    continue

                if cleaned_sanskrit and not has_devanagari:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - SKIPPED (no Devanagari characters)"
                        )
                    )
                    skipped += 1
                    continue

                # Validate required fields according to model constraints
                # Model requires: book_name, chapter_number >= 1, verse_number >= 1, sanskrit_text
                if not cleaned_sanskrit:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - SKIPPED (missing sanskrit_text)"
                        )
                    )
                    skipped += 1
                    continue

                # Validate chapter_number and verse_number >= 1 (MinValueValidator constraint)
                if not chapter_num_extracted or chapter_num_extracted < 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - SKIPPED (invalid chapter_number, must be >= 1)"
                        )
                    )
                    skipped += 1
                    continue

                if not verse_num or verse_num < 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - SKIPPED (invalid verse_number, must be >= 1)"
                        )
                    )
                    skipped += 1
                    continue

                # Ensure transliteration is None if empty (model allows null=True)
                # Model: transliteration = models.TextField(blank=True, null=True)
                # Convert empty string to None to match model's null=True behavior
                transliteration_value = None
                if cleaned_transliteration and cleaned_transliteration.strip():
                    transliteration_value = cleaned_transliteration.strip()

                # Prepare data in exact model format matching Shloka model structure:
                # - book_name: TextField (required) - no max length
                # - chapter_number: IntegerField with MinValueValidator(1) (required)
                # - verse_number: IntegerField with MinValueValidator(1) (required)
                # - sanskrit_text: TextField (required) - no max length
                # - transliteration: TextField(blank=True, null=True) (optional) - None if empty
                # - id: UUIDField (auto-generated)
                # - created_at, updated_at: DateTimeField (auto-generated via TimestampedModel)
                shloka_data_dict = {
                    'book_name': str(book_name).strip(),  # TextField (required)
                    'chapter_number': int(chapter_num_extracted),  # IntegerField >= 1 (required)
                    'verse_number': int(verse_num),  # IntegerField >= 1 (required)
                    'sanskrit_text': str(cleaned_sanskrit).strip(),  # TextField (required)
                    'transliteration': transliteration_value,  # TextField(blank=True, null=True) - None if empty
                }

                # Save to database using get_or_create with exact model format
                # Model has index on (book_name, chapter_number, verse_number) which ensures uniqueness
                # get_or_create will return existing shloka if combination already exists
                if not dry_run:
                    with transaction.atomic():
                        # Use get_or_create with lookup fields matching the model's unique index
                        # Lookup: (book_name, chapter_number, verse_number)
                        # Defaults: All fields including sanskrit_text and transliteration
                        shloka, created = Shloka.objects.get_or_create(
                            book_name=book_name,
                            chapter_number=chapter_num_extracted,
                            verse_number=verse_num,
                            defaults=shloka_data_dict,
                        )

                        if created:
                            added += 1
                            existing_shlokas.add(
                                (chapter_num_extracted, verse_num)
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"    ✓ Shloka {idx}: Chapter {chapter_num_extracted}, "
                                    f"Verse {verse_num} - Saved (ID: {shloka.id})"
                                )
                            )
                            
                            # Generate and save explanations immediately for consistency
                            if not dry_run and not skip_explanations:
                                self._generate_explanations_for_shloka(
                                    shloka_service, shloka, verbose
                                )
                        else:
                            skipped += 1
                            self.stdout.write(
                                f"    Shloka {idx}: Chapter {chapter_num_extracted}, "
                                f"Verse {verse_num} - Already exists"
                            )
                            
                            # Create explanation for existing shloka if it doesn't have one
                            if not dry_run and not skip_explanations and create_explanations_for_existing:
                                from apps.sanatan_app.models import ShlokaExplanation
                                has_explanation = ShlokaExplanation.objects.filter(shloka=shloka).exists()
                                if not has_explanation:
                                    if verbose:
                                        self.stdout.write(
                                            f"      Creating explanation for existing shloka..."
                                        )
                                    self._generate_explanations_for_shloka(
                                        shloka_service, shloka, verbose
                                    )
                                elif verbose:
                                    self.stdout.write(
                                        f"      Shloka already has explanation, skipping"
                                    )
                else:
                    # Dry run - just validate
                    added += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    ✓ Shloka {idx}: Chapter {chapter_num_extracted}, "
                            f"Verse {verse_num} - Would be saved (DRY RUN)"
                        )
                    )

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"    ✗ Shloka {idx}: Error - {str(e)}"
                    )
                )
                logger.exception(e)

        # After processing all shlokas, create explanations for existing shlokas if requested
        if not dry_run and not skip_explanations and create_explanations_for_existing:
            from apps.sanatan_app.models import ShlokaExplanation
            self.stdout.write("  Creating explanations for existing shlokas without explanations...")
            existing_shlokas_in_chapter = Shloka.objects.filter(
                book_name=book_name,
                chapter_number=chapter_num
            )
            explanations_created = 0
            for existing_shloka in existing_shlokas_in_chapter:
                has_explanation = ShlokaExplanation.objects.filter(shloka=existing_shloka).exists()
                if not has_explanation:
                    try:
                        if verbose:
                            self.stdout.write(
                                f"    Creating explanation for Chapter {chapter_num}, "
                                f"Verse {existing_shloka.verse_number}..."
                            )
                        self._generate_explanations_for_shloka(
                            shloka_service, existing_shloka, verbose
                        )
                        explanations_created += 1
                    except Exception as e:
                        logger.warning(
                            f"Failed to create explanation for existing shloka "
                            f"{existing_shloka.id}: {str(e)}"
                        )
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"      ⚠ Failed to create explanation: {str(e)}"
                                )
                            )
            if explanations_created > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created {explanations_created} explanation(s) for existing shlokas"
                    )
                )

        return added, skipped, errors

    def _generate_explanations_for_shloka(self, shloka_service, shloka, verbose=False):
        """
        Generate and save structured explanation for a shloka.
        
        This ensures all shlokas have consistent explanations generated at extraction time.
        Verifies that all explanation fields are properly saved.
        """
        explanations_generated = 0
        explanations_failed = 0
        
        # Generate structured explanation (single explanation per shloka now)
        try:
            if verbose:
                self.stdout.write(
                    f"      Generating explanation for Chapter {shloka.chapter_number}, "
                    f"Verse {shloka.verse_number}..."
                )
            
            explanation = shloka_service.generate_and_store_explanation(shloka)
            if explanation:
                explanations_generated += 1
                # Verify all fields are saved
                fields_status = self._verify_explanation_fields(explanation)
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"      ✓ Explanation generated (ID: {explanation.id})"
                        )
                    )
                    self._log_explanation_fields(explanation, fields_status)
                elif not all(fields_status.values()):
                    # Log warning if some fields are missing even in non-verbose mode
                    missing_fields = [field for field, present in fields_status.items() if not present]
                    self.stdout.write(
                        self.style.WARNING(
                            f"      ⚠ Explanation missing fields: {', '.join(missing_fields)}"
                        )
                    )
            else:
                explanations_failed += 1
                if verbose:
                    self.stdout.write(
                        self.style.WARNING(
                            f"      ⚠ Explanation generation returned None"
                        )
                    )
        except Exception as e:
            explanations_failed += 1
            logger.warning(
                f"Failed to generate explanation for shloka {shloka.id}: {str(e)}"
            )
            if verbose:
                self.stdout.write(
                    self.style.WARNING(
                        f"      ⚠ Failed to generate explanation: {str(e)}"
                    )
                )
        
        if not verbose and explanations_generated > 0:
            self.stdout.write(
                f"      ✓ Generated explanation for shloka"
            )
        
        if explanations_failed > 0:
            logger.warning(
                f"Failed to generate explanation for shloka {shloka.id}"
            )
    
    def _verify_explanation_fields(self, explanation):
        """
        Verify that all expected fields are present in the explanation.
        
        Returns a dict with field names as keys and boolean indicating presence.
        Note: word_by_word is stored on the Shloka model, not the explanation.
        We check it separately and don't include it in explanation fields verification.
        """
        fields_status = {
            'summary': bool(explanation.summary),
            'detailed_meaning': bool(explanation.detailed_meaning),
            'detailed_explanation': bool(explanation.detailed_explanation),
            'context': bool(explanation.context),
            'why_this_matters': bool(explanation.why_this_matters),
            'modern_examples': bool(explanation.modern_examples),
            'themes': bool(explanation.themes),
            'reflection_prompt': bool(explanation.reflection_prompt),
            'ai_model_used': bool(explanation.ai_model_used),
            'generation_prompt': bool(explanation.generation_prompt),
        }
        return fields_status
    
    def _log_explanation_fields(self, explanation, fields_status):
        """Log the status of all explanation fields."""
        self.stdout.write(f"        Explanation fields status:")
        for field, present in fields_status.items():
            status_icon = "✓" if present else "✗"
            status_style = self.style.SUCCESS if present else self.style.WARNING
            field_value_preview = ""
            if present:
                field_value = getattr(explanation, field, None)
                if field_value:
                    if isinstance(field_value, (list, dict)):
                        field_value_preview = f" ({len(field_value)} items)"
                    elif isinstance(field_value, str):
                        field_value_preview = f" ({len(field_value)} chars)"
            self.stdout.write(
                status_style(f"          {status_icon} {field}: {'Present' + field_value_preview if present else 'Missing'}")
            )
        
        # Log word_by_word separately since it's stored on Shloka, not explanation
        word_by_word_present = bool(explanation.shloka.word_by_word if hasattr(explanation.shloka, 'word_by_word') else False)
        status_icon = "✓" if word_by_word_present else "✗"
        status_style = self.style.SUCCESS if word_by_word_present else self.style.WARNING
        word_count = ""
        if word_by_word_present:
            word_count = f" ({len(explanation.shloka.word_by_word)} items on Shloka)"
        self.stdout.write(
            status_style(f"          {status_icon} word_by_word (on Shloka): {'Present' + word_count if word_by_word_present else 'Missing'}")
        )

    def _find_chapter_start_page(self, pdf_reader, chapter_num):
        """
        Find the starting page number for a chapter.
        
        This method intelligently finds the actual chapter content, not the table of contents.
        It looks for:
        1. Chapter markers (Chapter X, CHAPTER X, etc.)
        2. Actual chapter content indicators (Sanskrit text, verse numbers, etc.)
        3. Excludes table of contents (TOC) pages
        """
        # Search for chapter markers
        chapter_patterns = [
            f'Chapter {chapter_num}',
            f'CHAPTER {chapter_num}',
            f'Ch. {chapter_num}',
            f'CH. {chapter_num}',
        ]
        
        # Patterns that indicate table of contents (TOC)
        toc_indicators = [
            'Contents',
            'CONTENTS',
            'Table of Contents',
            'TABLE OF CONTENTS',
            'Preface',
            'Introduction',
            'CHAPTER 2',  # If we see multiple chapters listed, it's likely TOC
            'CHAPTER 3',
        ]
        
        # Patterns that indicate actual chapter content
        content_indicators = [
            'VERSE',
            'verse',
            'Verse',
            'श्लोक',  # Shloka in Devanagari
            'Text:',  # Some PDFs have "Text:" before Sanskrit
        ]

        # Search in estimated range (wider search for first chapters)
        # For Chapter 1, start from page 0, for others use estimated
        if chapter_num == 1:
            search_start = 0
            search_end = min(50, len(pdf_reader.pages))  # Search first 50 pages for Chapter 1
        else:
            estimated_start = (chapter_num - 1) * 15
            search_start = max(0, estimated_start - 10)
            search_end = min(estimated_start + 30, len(pdf_reader.pages))

        candidate_pages = []
        
        for page_num in range(search_start, search_end):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()

                if not page_text:
                    continue
                
                # Check if this page has chapter marker
                has_chapter_marker = False
                for pattern in chapter_patterns:
                    if pattern in page_text:
                        has_chapter_marker = True
                        break
                
                if not has_chapter_marker:
                    continue
                
                # Check if this looks like TOC (exclude it)
                is_toc = False
                for toc_indicator in toc_indicators:
                    if toc_indicator in page_text:
                        # Additional check: if page has chapter numbers but also has TOC indicators
                        # and doesn't have much content, it's likely TOC
                        if len(page_text) < 1000:  # TOC pages are usually short
                            is_toc = True
                            break
                
                if is_toc:
                    continue
                
                # Check if this page has actual content indicators
                has_content = False
                content_score = 0
                
                # Check for Sanskrit/Devanagari characters
                has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in page_text)
                if has_devanagari:
                    content_score += 3
                    has_content = True
                
                # Check for verse markers
                for indicator in content_indicators:
                    if indicator in page_text:
                        content_score += 2
                        has_content = True
                
                # Check for verse numbers (like "1.", "2.", "Verse 1", etc.)
                verse_patterns = [
                    rf'\b{chapter_num}\.\d+',  # Chapter.Verse like "1.1", "1.2"
                    rf'Verse\s+{chapter_num}\.\d+',
                    rf'VERSE\s+{chapter_num}\.\d+',
                ]
                for pattern in verse_patterns:
                    if re.search(pattern, page_text):
                        content_score += 2
                        has_content = True
                        break
                
                # If we found chapter marker and content indicators, this is likely the real chapter
                if has_content and content_score >= 2:
                    candidate_pages.append((page_num, content_score))
                    
            except Exception as e:
                logger.debug(f"Error checking page {page_num}: {str(e)}")
                continue
        
        # Return the page with highest content score (most likely to be actual chapter)
        if candidate_pages:
            # Sort by content score (descending) and return the first one
            candidate_pages.sort(key=lambda x: x[1], reverse=True)
            best_page = candidate_pages[0][0]
            logger.info(f"Found Chapter {chapter_num} at page {best_page} (score: {candidate_pages[0][1]})")
            return best_page
        
        # Fallback: if no good candidate found, try simple pattern matching
        # but skip obvious TOC pages
        for page_num in range(search_start, min(search_start + 30, len(pdf_reader.pages))):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if not page_text:
                    continue
                
                # Skip if it looks like TOC
                if any(toc in page_text for toc in toc_indicators) and len(page_text) < 1000:
                    continue
                
                # Check for chapter marker
                for pattern in chapter_patterns:
                    if pattern in page_text:
                        # Additional check: page should have some substantial content
                        if len(page_text) > 500:  # Real chapters have more content
                            return page_num
            except Exception:
                continue

        return None

