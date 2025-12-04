"""
Django management command to ensure all shlokas have both summary and detailed explanations
with consistent formatting (including Meaning, Explanation, Examples sections).
Run: python manage.py ensure_shloka_explanations
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.sanatan_app.models import Shloka, ShlokaExplanation, ReadingType
from apps.sanatan_app.services.shloka_service import ShlokaService
import time
import re


class Command(BaseCommand):
    help = 'Ensure all shlokas have both summary and detailed explanations with consistent formatting'

    def _validate_explanation_format(self, explanation_text, explanation_type):
        """
        Validate that an explanation follows the expected format structure.
        
        Returns:
            tuple: (is_valid, missing_sections)
        """
        if not explanation_text:
            return False, ["empty explanation"]
        
        text_lower = explanation_text.lower()
        missing_sections = []
        
        # ALL explanations MUST have these 5 sections: Meaning, Word-by-word, Explanation, Practical Application, Example
        # Note: Handle both regular hyphens (-) and non-breaking hyphens (‑) in section headers
        if explanation_type == ReadingType.DETAILED:
            # Check for required sections in detailed explanations
            required_sections = [
                ("meaning", ["meaning"]),
                ("word-by-word", ["word[-‑]by[-‑]word", "statement[-‑]by[-‑]statement", "breakdown", "word by word"]),
                ("explanation", ["explanation"]),
                ("practical application", ["practical application", "application"]),
                ("examples", ["example", "examples"])
            ]
        else:  # SUMMARY
            # Check for required sections in summary explanations
            required_sections = [
                ("meaning", ["meaning"]),
                ("word-by-word", ["word[-‑]by[-‑]word", "word by word"]),
                ("explanation", ["explanation"]),
                ("practical application", ["practical application", "application"]),
                ("example", ["example", "examples"])
            ]
        
        for section_name, keywords in required_sections:
            found = False
            for keyword in keywords:
                # Normalize keyword pattern - replace [-‑] with a pattern that matches both regular and non-breaking hyphens
                # Also handle spaces in "word by word"
                keyword_pattern = keyword.replace('[-‑]', r'[-‑\s]+')  # Match hyphens or spaces
                
                # Check for section headers with various formats:
                # - Numbered: "1. WORD-BY-WORD", "2. Word‑by‑word"
                # - With colons: "WORD-BY-WORD:", "Word‑by‑word:"
                # - Markdown bold: "**WORD-BY-WORD**", "**Word‑by‑word**"
                # - With dashes/underscores: "WORD-BY-WORD", "WORD_BY_WORD"
                # Look for keyword at start of line (possibly numbered) followed by colon, markdown, or newline
                
                # Pattern 1: Numbered headers (1., 2., etc.) with optional markdown
                # Use keyword_pattern directly (it may contain regex)
                pattern1 = rf'(?:^|\n)\s*(?:\d+\.\s*)?(?:\*\*)?\s*{keyword_pattern}\s*(?:\*\*)?[:\s\-‑]'
                if re.search(pattern1, text_lower, re.MULTILINE | re.IGNORECASE):
                    found = True
                    break
                
                # Pattern 2: Markdown bold headers (**WORD-BY-WORD** or **WORD‑BY‑WORD**)
                pattern2 = rf'\*\*{keyword_pattern}\*\*'
                if re.search(pattern2, text_lower, re.IGNORECASE):
                    found = True
                    break
                
                # Pattern 3: Headers with colons (WORD-BY-WORD: or WORD‑BY‑WORD:)
                pattern3 = rf'(?:^|\n)\s*{keyword_pattern}\s*:'
                if re.search(pattern3, text_lower, re.MULTILINE | re.IGNORECASE):
                    found = True
                    break
                
                # Pattern 4: Word boundary check for keywords that might be formatted differently
                # For patterns with hyphens/spaces, use a more flexible approach
                if '[-‑]' in keyword or ' ' in keyword:
                    # For multi-word patterns, check if all parts appear near each other
                    parts = re.split(r'[-‑\s]+', keyword)
                    if len(parts) > 1:
                        # Check if all parts appear in sequence (allowing for hyphens/spaces between)
                        flexible_pattern = r'\s*[-‑\s]+\s*'.join([re.escape(part) for part in parts])
                        pattern4 = rf'(?:^|\n)\s*(?:\d+\.\s*)?(?:\*\*)?\s*{flexible_pattern}\s*(?:\*\*)?[:\s\-‑]'
                        if re.search(pattern4, text_lower, re.MULTILINE | re.IGNORECASE):
                            found = True
                            break
                else:
                    # Single word - use word boundary
                    word_boundary_pattern = rf'\b{re.escape(keyword)}\b'
                    matches = list(re.finditer(word_boundary_pattern, text_lower, re.IGNORECASE))
                    # If found, check if it's likely a section header (near start of line or after number)
                    for match in matches:
                        start = match.start()
                        # Check if it's near the start of a line (within 40 chars to catch more variations)
                        line_start = text_lower.rfind('\n', 0, start) + 1
                        if start - line_start < 40:
                            # Additional check: make sure it's not in the middle of a sentence
                            line_text_before = text_lower[line_start:start]
                            # Allow for markdown formatting, numbers, and common header patterns
                            if (not re.search(r'[.!?]\s*$', line_text_before) or 
                                re.search(r'^\s*(?:\d+\.\s*)?(?:\*\*)?\s*$', line_text_before)):
                                found = True
                                break
                if found:
                    break
            if not found:
                missing_sections.append(section_name)
        
        is_valid = len(missing_sections) == 0
        return is_valid, missing_sections

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating explanations',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of shlokas to process before showing progress (default: 10)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay in seconds between API calls to avoid rate limiting (default: 0.5)',
        )
        parser.add_argument(
            '--check-format',
            action='store_true',
            help='Check format consistency and regenerate explanations that don\'t match expected format',
        )
        parser.add_argument(
            '--regenerate-all',
            action='store_true',
            help='Regenerate all explanations regardless of whether they exist (forces format consistency)',
        )

    def handle(self, *args, **options):
        """Ensure all shlokas have both summary and detailed explanations with consistent formatting."""
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        delay = options['delay']
        check_format = options['check_format']
        regenerate_all = options['regenerate_all']
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Ensuring all shlokas have consistent explanations"))
        self.stdout.write("=" * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No explanations will be generated"))
        if regenerate_all:
            self.stdout.write(self.style.WARNING("REGENERATE ALL MODE - All explanations will be regenerated"))
        if check_format:
            self.stdout.write(self.style.WARNING("FORMAT CHECK MODE - Will validate and fix format inconsistencies"))
        
        # Initialize service
        shloka_service = ShlokaService()
        
        # Get all shlokas
        all_shlokas = Shloka.objects.all().order_by('book_name', 'chapter_number', 'verse_number')
        total_count = all_shlokas.count()
        
        self.stdout.write(f"\nTotal shlokas in database: {total_count}")
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING("No shlokas found in database."))
            return
        
        # Find shlokas missing explanations or with format issues
        shlokas_missing_summary = []
        shlokas_missing_detailed = []
        shlokas_invalid_format_summary = []
        shlokas_invalid_format_detailed = []
        shlokas_complete = []
        
        self.stdout.write("\nAnalyzing shlokas...")
        
        for shloka in all_shlokas:
            summary_explanation = ShlokaExplanation.objects.filter(
                shloka=shloka,
                explanation_type=ReadingType.SUMMARY
            ).first()
            
            detailed_explanation = ShlokaExplanation.objects.filter(
                shloka=shloka,
                explanation_type=ReadingType.DETAILED
            ).first()
            
            # Check summary
            if regenerate_all or not summary_explanation:
                shlokas_missing_summary.append(shloka)
            elif check_format and summary_explanation:
                is_valid, missing = self._validate_explanation_format(
                    summary_explanation.explanation_text, ReadingType.SUMMARY
                )
                if not is_valid:
                    shlokas_invalid_format_summary.append((shloka, missing))
            
            # Check detailed
            if regenerate_all or not detailed_explanation:
                shlokas_missing_detailed.append(shloka)
            elif check_format and detailed_explanation:
                is_valid, missing = self._validate_explanation_format(
                    detailed_explanation.explanation_text, ReadingType.DETAILED
                )
                if not is_valid:
                    shlokas_invalid_format_detailed.append((shloka, missing))
            
            # Track complete ones (only if not regenerating all)
            if not regenerate_all and summary_explanation and detailed_explanation:
                if not check_format:
                    shlokas_complete.append(shloka)
                else:
                    # Only count as complete if format is valid
                    summary_valid, _ = self._validate_explanation_format(
                        summary_explanation.explanation_text, ReadingType.SUMMARY
                    )
                    detailed_valid, _ = self._validate_explanation_format(
                        detailed_explanation.explanation_text, ReadingType.DETAILED
                    )
                    if summary_valid and detailed_valid:
                        shlokas_complete.append(shloka)
        
        # Print summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("ANALYSIS SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"✓ Complete (both explanations with valid format): {len(shlokas_complete)}")
        self.stdout.write(f"✗ Missing summary: {len(shlokas_missing_summary)}")
        self.stdout.write(f"✗ Missing detailed: {len(shlokas_missing_detailed)}")
        if check_format:
            self.stdout.write(f"⚠ Invalid format summary: {len(shlokas_invalid_format_summary)}")
            self.stdout.write(f"⚠ Invalid format detailed: {len(shlokas_invalid_format_detailed)}")
        self.stdout.write("=" * 70)
        
        # Show format issues if checking format
        if check_format and (shlokas_invalid_format_summary or shlokas_invalid_format_detailed):
            self.stdout.write("\nFormat Issues Found:")
            for shloka, missing in shlokas_invalid_format_summary:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Summary - {shloka.book_name} Ch.{shloka.chapter_number}, V.{shloka.verse_number}: "
                        f"Missing sections: {', '.join(missing)}"
                    )
                )
            for shloka, missing in shlokas_invalid_format_detailed:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Detailed - {shloka.book_name} Ch.{shloka.chapter_number}, V.{shloka.verse_number}: "
                        f"Missing sections: {', '.join(missing)}"
                    )
                )
        
        # Combine missing and invalid format lists
        shlokas_to_regenerate_summary = shlokas_missing_summary + [s[0] for s in shlokas_invalid_format_summary]
        shlokas_to_regenerate_detailed = shlokas_missing_detailed + [s[0] for s in shlokas_invalid_format_detailed]
        
        # Remove duplicates
        shlokas_to_regenerate_summary = list(dict.fromkeys(shlokas_to_regenerate_summary))
        shlokas_to_regenerate_detailed = list(dict.fromkeys(shlokas_to_regenerate_detailed))
        
        if not shlokas_to_regenerate_summary and not shlokas_to_regenerate_detailed:
            self.stdout.write(self.style.SUCCESS("\n✓ All shlokas already have both explanations with consistent format!"))
            return
        
        if dry_run:
            self.stdout.write("\n" + self.style.WARNING("DRY RUN - Would generate/regenerate:"))
            if shlokas_to_regenerate_summary:
                self.stdout.write(f"  - {len(shlokas_to_regenerate_summary)} summary explanations")
            if shlokas_to_regenerate_detailed:
                self.stdout.write(f"  - {len(shlokas_to_regenerate_detailed)} detailed explanations")
            return
        
        # Delete existing explanations if regenerating (for format consistency)
        if regenerate_all or check_format:
            if shlokas_invalid_format_summary:
                self.stdout.write(f"\nDeleting {len(shlokas_invalid_format_summary)} summary explanations with invalid format...")
                for shloka, _ in shlokas_invalid_format_summary:
                    ShlokaExplanation.objects.filter(
                        shloka=shloka,
                        explanation_type=ReadingType.SUMMARY
                    ).delete()
            
            if shlokas_invalid_format_detailed:
                self.stdout.write(f"Deleting {len(shlokas_invalid_format_detailed)} detailed explanations with invalid format...")
                for shloka, _ in shlokas_invalid_format_detailed:
                    ShlokaExplanation.objects.filter(
                        shloka=shloka,
                        explanation_type=ReadingType.DETAILED
                    ).delete()
        
        # Generate missing explanations
        total_to_generate = len(shlokas_to_regenerate_summary) + len(shlokas_to_regenerate_detailed)
        generated_count = 0
        failed_count = 0
        
        self.stdout.write(f"\nGenerating {total_to_generate} explanations...")
        self.stdout.write(f"Delay between API calls: {delay}s\n")
        
        # Generate summaries
        if shlokas_to_regenerate_summary:
            self.stdout.write(f"\n{'=' * 70}")
            self.stdout.write(f"GENERATING SUMMARY EXPLANATIONS ({len(shlokas_to_regenerate_summary)} shlokas)")
            self.stdout.write(f"{'=' * 70}\n")
            
            for idx, shloka in enumerate(shlokas_to_regenerate_summary, 1):
                try:
                    self.stdout.write(
                        f"[{idx}/{len(shlokas_missing_summary)}] "
                        f"Generating summary for {shloka.book_name} "
                        f"Ch.{shloka.chapter_number}, V.{shloka.verse_number}...",
                        ending=' '
                    )
                    
                    explanation = shloka_service.get_explanation(shloka.id, ReadingType.SUMMARY)
                    
                    if explanation:
                        generated_count += 1
                        self.stdout.write(self.style.SUCCESS("✓"))
                    else:
                        failed_count += 1
                        self.stdout.write(self.style.ERROR("✗ (Connection error)"))
                    
                    # Show progress every batch_size
                    if idx % batch_size == 0:
                        self.stdout.write(f"\nProgress: {idx}/{len(shlokas_to_regenerate_summary)} processed")
                    
                    # Delay to avoid rate limiting
                    if idx < len(shlokas_to_regenerate_summary):
                        time.sleep(delay)
                        
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                    # Continue with next shloka
                    continue
        
        # Generate detailed explanations
        if shlokas_to_regenerate_detailed:
            self.stdout.write(f"\n{'=' * 70}")
            self.stdout.write(f"GENERATING DETAILED EXPLANATIONS ({len(shlokas_to_regenerate_detailed)} shlokas)")
            self.stdout.write(f"{'=' * 70}\n")
            
            for idx, shloka in enumerate(shlokas_to_regenerate_detailed, 1):
                try:
                    self.stdout.write(
                        f"[{idx}/{len(shlokas_missing_detailed)}] "
                        f"Generating detailed explanation for {shloka.book_name} "
                        f"Ch.{shloka.chapter_number}, V.{shloka.verse_number}...",
                        ending=' '
                    )
                    
                    explanation = shloka_service.get_explanation(shloka.id, ReadingType.DETAILED)
                    
                    if explanation:
                        generated_count += 1
                        self.stdout.write(self.style.SUCCESS("✓"))
                    else:
                        failed_count += 1
                        self.stdout.write(self.style.ERROR("✗ (Connection error)"))
                    
                    # Show progress every batch_size
                    if idx % batch_size == 0:
                        self.stdout.write(f"\nProgress: {idx}/{len(shlokas_to_regenerate_detailed)} processed")
                    
                    # Delay to avoid rate limiting
                    if idx < len(shlokas_to_regenerate_detailed):
                        time.sleep(delay)
                        
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                    # Continue with next shloka
                    continue
        
        # Final summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("FINAL SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"✓ Successfully generated: {generated_count}")
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ Failed: {failed_count}"))
        self.stdout.write("=" * 70)
        
        # Verify final state
        self.stdout.write("\nVerifying final state...")
        all_shloka_ids = set(Shloka.objects.values_list('id', flat=True))
        shlokas_with_summary = set(
            ShlokaExplanation.objects.filter(explanation_type=ReadingType.SUMMARY)
            .values_list('shloka_id', flat=True)
        )
        shlokas_with_detailed = set(
            ShlokaExplanation.objects.filter(explanation_type=ReadingType.DETAILED)
            .values_list('shloka_id', flat=True)
        )
        remaining_missing_summary = len(all_shloka_ids - shlokas_with_summary)
        remaining_missing_detailed = len(all_shloka_ids - shlokas_with_detailed)
        
        # Check format if requested
        format_issues = 0
        if check_format:
            self.stdout.write("Checking format consistency...")
            for shloka_id in shlokas_with_summary:
                explanation = ShlokaExplanation.objects.filter(
                    shloka_id=shloka_id,
                    explanation_type=ReadingType.SUMMARY
                ).first()
                if explanation:
                    is_valid, _ = self._validate_explanation_format(
                        explanation.explanation_text, ReadingType.SUMMARY
                    )
                    if not is_valid:
                        format_issues += 1
            
            for shloka_id in shlokas_with_detailed:
                explanation = ShlokaExplanation.objects.filter(
                    shloka_id=shloka_id,
                    explanation_type=ReadingType.DETAILED
                ).first()
                if explanation:
                    is_valid, _ = self._validate_explanation_format(
                        explanation.explanation_text, ReadingType.DETAILED
                    )
                    if not is_valid:
                        format_issues += 1
        
        if remaining_missing_summary == 0 and remaining_missing_detailed == 0:
            if check_format and format_issues == 0:
                self.stdout.write(self.style.SUCCESS("\n✓ All shlokas now have both explanations with consistent format!"))
            elif check_format:
                self.stdout.write(self.style.WARNING(
                    f"\n⚠ All shlokas have explanations, but {format_issues} still have format issues."
                ))
                self.stdout.write("Run with --check-format again to fix them.")
            else:
                self.stdout.write(self.style.SUCCESS("\n✓ All shlokas now have both explanations!"))
        else:
            self.stdout.write(self.style.WARNING(
                f"\n⚠ Still missing: {remaining_missing_summary} summaries, "
                f"{remaining_missing_detailed} detailed explanations"
            ))
            self.stdout.write("You may need to run this command again if there were connection errors.")

