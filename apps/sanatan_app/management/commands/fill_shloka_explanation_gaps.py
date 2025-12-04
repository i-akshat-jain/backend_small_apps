"""
Django management command to fill gaps in ShlokaExplanation records.

This command goes through all existing ShlokaExplanation records and fills in
missing optional structured fields (why_this_matters, context, word_by_word,
modern_examples, themes, reflection_prompt).

It does NOT regenerate explanations - only fills empty/null fields using the shloka data.

Run: python manage.py fill_shloka_explanation_gaps
"""
from django.core.management.base import BaseCommand
from apps.sanatan_app.models import Shloka, ShlokaExplanation, ReadingType
from apps.sanatan_app.groq_service import GroqService
from apps.sanatan_app.services.shloka_service import ShlokaService
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fill gaps in existing ShlokaExplanation records (missing optional structured fields)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually updating explanations',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay in seconds between API calls to avoid rate limiting (default: 0.5)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each explanation',
        )
        parser.add_argument(
            '--shloka-id',
            type=str,
            default=None,
            help='Test on a specific shloka ID (UUID format). If provided, only this shloka will be processed.',
        )

    def _has_missing_fields(self, explanation):
        """
        Check if an explanation is missing any optional structured fields.
        
        Note: word_by_word is now stored on the Shloka model, not the explanation.
        
        Returns:
            tuple: (has_missing, missing_fields_list)
        """
        optional_fields = [
            'why_this_matters',
            'context',
            'word_by_word',  # Checked on shloka, not explanation
            'modern_examples',
            'themes',
            'reflection_prompt',
        ]
        
        missing_fields = []
        for field in optional_fields:
            # word_by_word is stored on shloka, not explanation
            if field == 'word_by_word':
                value = explanation.shloka.word_by_word if hasattr(explanation.shloka, 'word_by_word') else None
            else:
                value = getattr(explanation, field, None)
            # Check if field is None, empty string, or empty list/dict
            if value is None or value == '' or (isinstance(value, (list, dict)) and len(value) == 0):
                missing_fields.append(field)
        
        return len(missing_fields) > 0, missing_fields

    def _generate_missing_fields(self, shloka, missing_fields, explanation_type):
        """
        Generate only the missing structured fields using the shloka data.
        
        Args:
            shloka: Shloka model instance
            missing_fields: List of field names to generate
            explanation_type: 'summary' or 'detailed'
            
        Returns:
            dict with generated field values
        """
        groq_service = GroqService()
        
        # Build a simple prompt asking for just the missing fields
        prompt_parts = [
            f"Provide the following information for this shloka from {shloka.book_name}",
            f"Chapter {shloka.chapter_number}, Verse {shloka.verse_number}:",
            "",
            "Sanskrit Text:",
            shloka.sanskrit_text,
        ]
        
        if shloka.transliteration:
            prompt_parts.extend([
                "",
                "Transliteration:",
                shloka.transliteration,
            ])
        
        prompt_parts.extend([
            "",
            "Please provide ONLY the following fields in a clear, structured format:",
            "",
        ])
        
        field_descriptions = {
            'word_by_word': "WORD-BY-WORD: Break down each word/phrase with its meaning. Format: '- **word** – meaning'",
            'context': "CONTEXT: The context of this verse in the dialogue/story (2-3 sentences)",
            'why_this_matters': "WHY THIS MATTERS: Modern relevance and practical importance (2-3 sentences)",
            'modern_examples': "MODERN EXAMPLES: 1-2 concrete examples from modern life. Format: '- Category: Description'",
            'themes': "THEMES: List of key themes (e.g., Dharma, Karma, Wisdom). Format: '- Theme1, Theme2, Theme3'",
            'reflection_prompt': "REFLECTION PROMPT: A thoughtful question for contemplation (1 sentence ending with ?)",
        }
        
        for field in missing_fields:
            if field in field_descriptions:
                prompt_parts.append(field_descriptions[field])
        
        prompt = "\n".join(prompt_parts)
        
        try:
            # Call Groq API
            response = groq_service.client.chat.completions.create(
                model=groq_service.model,
                messages=[
                    {"role": "system", "content": groq_service.SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt}
                ],
                temperature=groq_service.TEMPERATURE,
                max_tokens=2000,
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse the response to extract structured fields
            result = {}
            
            # Extract word_by_word
            if 'word_by_word' in missing_fields:
                word_by_word = groq_service._parse_word_by_word(response_text)
                if word_by_word:
                    result['word_by_word'] = word_by_word
            
            # Extract context
            if 'context' in missing_fields:
                context = self._extract_section(response_text, ['CONTEXT'])
                if context:
                    result['context'] = context
            
            # Extract why_this_matters
            if 'why_this_matters' in missing_fields:
                why_matters = self._extract_section(response_text, ['WHY THIS MATTERS', 'PRACTICAL APPLICATION'])
                if why_matters:
                    result['why_this_matters'] = why_matters
            
            # Extract modern_examples
            if 'modern_examples' in missing_fields:
                examples = groq_service._parse_modern_examples(response_text)
                if examples:
                    result['modern_examples'] = examples
            
            # Extract themes
            if 'themes' in missing_fields:
                themes = groq_service._extract_themes(response_text)
                if themes:
                    result['themes'] = themes
            
            # Extract reflection_prompt
            if 'reflection_prompt' in missing_fields:
                prompt_text = self._extract_section(response_text, ['REFLECTION PROMPT', 'REFLECTION'])
                if prompt_text:
                    result['reflection_prompt'] = prompt_text
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating missing fields: {str(e)}")
            return {}
    
    def _extract_section(self, text, section_names):
        """Extract a section from text by section name."""
        lines = text.split('\n')
        in_section = False
        section_lines = []
        
        for line in lines:
            line_upper = line.upper().strip()
            # Check if this line is a section header
            if any(name.upper() in line_upper for name in section_names):
                in_section = True
                # Skip the header line itself
                continue
            
            if in_section:
                # Check if we hit another section header
                if ':' in line and any(
                    line_upper.startswith(f"{i}. ") or line_upper.startswith(f"{i}.")
                    for i in range(1, 10)
                ):
                    break
                if line.strip():
                    section_lines.append(line.strip())
        
        return '\n'.join(section_lines).strip() if section_lines else None
    
    def _has_word_by_word_section(self, explanation_text):
        """
        Check if explanation text contains a WORD-BY-WORD section.
        
        Word-by-word should only be in the Shloka model, not in explanations.
        
        Returns:
            bool: True if word-by-word section is found, False otherwise
        """
        if not explanation_text:
            return False
        
        import re
        
        lines = explanation_text.split('\n')
        for line in lines:
            line_upper = line.upper().strip()
            # Check if this line is a WORD-BY-WORD section header
            is_word_by_word_header = (
                re.match(r'^\d+\.\s*WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                re.match(r'^WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                'WORD-BY-WORD' in line_upper or
                'WORD BY WORD' in line_upper or
                'STATEMENT-BY-STATEMENT' in line_upper
            )
            if is_word_by_word_header:
                return True
        
        return False
    
    def _remove_word_by_word_section(self, explanation_text):
        """
        Remove the WORD-BY-WORD section from explanation text.
        
        Word-by-word breakdown is stored only in the Shloka model, not in explanations.
        This method removes the WORD-BY-WORD section from the explanation text.
        
        Args:
            explanation_text: The full explanation text that may contain WORD-BY-WORD section
            
        Returns:
            Explanation text with WORD-BY-WORD section removed
        """
        if not explanation_text:
            return explanation_text
        
        import re
        
        # Use the same section extraction logic as groq_service to find and remove WORD-BY-WORD section
        lines = explanation_text.split('\n')
        cleaned_lines = []
        skip_until_next_section = False
        
        for line in lines:
            # Check if this line starts a WORD-BY-WORD section
            # Match patterns like "2. WORD-BY-WORD:", "WORD-BY-WORD:", "2. WORD-BY-WORD / STATEMENT-BY-STATEMENT BREAKDOWN:", etc.
            line_upper = line.upper().strip()
            is_word_by_word_header = (
                re.match(r'^\d+\.\s*WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                re.match(r'^WORD[-‑\s]*BY[-‑\s]*WORD', line_upper) or
                'WORD-BY-WORD' in line_upper or
                'WORD BY WORD' in line_upper or
                'STATEMENT-BY-STATEMENT' in line_upper
            )
            
            if is_word_by_word_header:
                # Start of WORD-BY-WORD section - skip it and all following lines until next section
                skip_until_next_section = True
                continue
            
            # If we're skipping (in WORD-BY-WORD section), check if we've reached the next section
            if skip_until_next_section:
                # Check if this is a new section header (starts with number and colon, or just uppercase text with colon)
                # But make sure it's not another WORD-BY-WORD variant
                line_upper_check = line.upper().strip()
                is_another_word_by_word = (
                    'WORD-BY-WORD' in line_upper_check or
                    'WORD BY WORD' in line_upper_check or
                    'STATEMENT-BY-STATEMENT' in line_upper_check
                )
                
                if not is_another_word_by_word:
                    # Check if this looks like a section header
                    is_new_section = (
                        re.match(r'^\d+\.\s+[A-Z][A-Z\s/-—\-‑]+:', line) or
                        re.match(r'^[A-Z][A-Z\s/-—\-‑]+:', line)
                    )
                    if is_new_section:
                        # We've reached the next section, stop skipping and include this line
                        skip_until_next_section = False
                        cleaned_lines.append(line)
                # Otherwise, continue skipping lines in the WORD-BY-WORD section
                continue
            
            # Not in WORD-BY-WORD section, keep the line
            cleaned_lines.append(line)
        
        # Join lines back together
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Clean up any double newlines that might have been created
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        
        # Remove trailing whitespace from each line
        cleaned_lines_final = [line.rstrip() for line in cleaned_text.split('\n')]
        cleaned_text = '\n'.join(cleaned_lines_final)
        
        return cleaned_text.strip()

    def handle(self, *args, **options):
        """Fill gaps in existing ShlokaExplanation records."""
        dry_run = options['dry_run']
        delay = options['delay']
        verbose = options['verbose']
        shloka_id = options.get('shloka_id')
        
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Filling Gaps in ShlokaExplanation Records"))
        self.stdout.write("=" * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No explanations will be updated"))
        
        # Get shlokas - filter by ID if provided
        if shloka_id:
            try:
                import uuid
                shloka_uuid = uuid.UUID(shloka_id)
                all_shlokas = Shloka.objects.filter(id=shloka_uuid).prefetch_related('explanations')
                total_shlokas = all_shlokas.count()
                
                if total_shlokas == 0:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Shloka with ID {shloka_id} not found in database.")
                    )
                    return
                
                self.stdout.write(f"\nTesting on specific shloka ID: {shloka_id}")
                shloka = all_shlokas.first()
                self.stdout.write(
                    f"  Shloka: {shloka.book_name} - Chapter {shloka.chapter_number}, Verse {shloka.verse_number}"
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"✗ Invalid shloka ID format: {shloka_id}. Expected UUID format.")
                )
                return
        else:
            # Get all shlokas with their explanations
            all_shlokas = Shloka.objects.all().prefetch_related('explanations').order_by(
                'book_name', 'chapter_number', 'verse_number'
            )
            total_shlokas = all_shlokas.count()
        
        self.stdout.write(f"\nTotal shlokas to process: {total_shlokas}")
        
        if total_shlokas == 0:
            self.stdout.write(self.style.WARNING("No shlokas found in database."))
            return
        
        # First pass: Check and clean word-by-word sections from explanations
        explanations_with_word_by_word = []
        cleaned_count = 0
        
        self.stdout.write("\nChecking for word-by-word sections in explanations...")
        
        for shloka in all_shlokas:
            shloka_explanations = shloka.explanations.all()
            
            if not shloka_explanations.exists():
                continue
            
            for explanation in shloka_explanations:
                if explanation.explanation_text and self._has_word_by_word_section(explanation.explanation_text):
                    explanations_with_word_by_word.append((shloka, explanation))
        
        if explanations_with_word_by_word:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(explanations_with_word_by_word)} explanation(s) with word-by-word sections that need cleaning"
                )
            )
            
            if not dry_run:
                self.stdout.write("Cleaning word-by-word sections from explanations...")
                for shloka, explanation in explanations_with_word_by_word:
                    cleaned_text = self._remove_word_by_word_section(explanation.explanation_text)
                    if cleaned_text != explanation.explanation_text:
                        explanation.explanation_text = cleaned_text
                        explanation.save(update_fields=['explanation_text', 'updated_at'])
                        cleaned_count += 1
                        if verbose:
                            self.stdout.write(
                                f"  ✓ Cleaned word-by-word from {shloka.book_name} Ch.{shloka.chapter_number}, "
                                f"V.{shloka.verse_number} ({explanation.get_explanation_type_display()})"
                            )
                
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Cleaned word-by-word sections from {cleaned_count} explanation(s)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN - Would clean word-by-word sections from {len(explanations_with_word_by_word)} explanation(s)"
                    )
                )
                if verbose:
                    for shloka, explanation in explanations_with_word_by_word[:10]:
                        self.stdout.write(
                            f"  - {shloka.book_name} Ch.{shloka.chapter_number}, "
                            f"V.{shloka.verse_number} ({explanation.get_explanation_type_display()})"
                        )
                    if len(explanations_with_word_by_word) > 10:
                        self.stdout.write(f"  ... and {len(explanations_with_word_by_word) - 10} more")
        else:
            self.stdout.write(self.style.SUCCESS("✓ No word-by-word sections found in explanations"))
        
        # Second pass: Check for missing explanation types (summary/detailed) and create them
        self.stdout.write("\nChecking for missing explanation types (summary/detailed)...")
        shloka_service = ShlokaService()
        missing_explanations = []
        created_explanations = []
        created_count = 0
        failed_creation_count = 0
        
        for shloka in all_shlokas:
            shloka_explanations = shloka.explanations.all()
            existing_types = {exp.explanation_type for exp in shloka_explanations}
            
            # Check for missing summary
            if ReadingType.SUMMARY not in existing_types:
                missing_explanations.append((shloka, ReadingType.SUMMARY))
            
            # Check for missing detailed
            if ReadingType.DETAILED not in existing_types:
                missing_explanations.append((shloka, ReadingType.DETAILED))
        
        if missing_explanations:
            self.stdout.write(
                self.style.WARNING(
                    f"Found {len(missing_explanations)} missing explanation(s) that need to be created"
                )
            )
            
            if not dry_run:
                self.stdout.write("Creating missing explanations...")
                for shloka, explanation_type in missing_explanations:
                    try:
                        if verbose:
                            self.stdout.write(
                                f"  → Creating {explanation_type} explanation for "
                                f"{shloka.book_name} Ch.{shloka.chapter_number}, V.{shloka.verse_number}...",
                                ending=' '
                            )
                        
                        explanation = shloka_service.generate_and_store_explanation(shloka, explanation_type)
                        
                        if explanation:
                            created_explanations.append((shloka, explanation, explanation_type))
                            created_count += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS("✓"))
                        else:
                            failed_creation_count += 1
                            if verbose:
                                self.stdout.write(self.style.WARNING("⚠ (Generation failed)"))
                        
                        # Delay to avoid rate limiting
                        time.sleep(delay)
                        
                    except Exception as e:
                        failed_creation_count += 1
                        if verbose:
                            self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                        else:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"✗ Error creating {explanation_type} for "
                                    f"{shloka.book_name} Ch.{shloka.chapter_number}, "
                                    f"V.{shloka.verse_number}: {str(e)}"
                                )
                            )
                        logger.exception(e)
                        continue
                
                if created_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Created {created_count} missing explanation(s)")
                    )
                if failed_creation_count > 0:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Failed to create {failed_creation_count} explanation(s)")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN - Would create {len(missing_explanations)} missing explanation(s)"
                    )
                )
                if verbose:
                    for shloka, explanation_type in missing_explanations[:10]:
                        self.stdout.write(
                            f"  - {shloka.book_name} Ch.{shloka.chapter_number}, "
                            f"V.{shloka.verse_number} ({explanation_type})"
                        )
                    if len(missing_explanations) > 10:
                        self.stdout.write(f"  ... and {len(missing_explanations) - 10} more")
        else:
            self.stdout.write(self.style.SUCCESS("✓ All shlokas have both summary and detailed explanations"))
        
        # Third pass: Analyze all shlokas and their explanations for missing fields
        explanations_with_gaps = []
        explanations_complete = []
        shlokas_with_gaps = []
        shlokas_complete = []
        
        self.stdout.write("\nAnalyzing shlokas and their explanations for missing fields...")
        
        for shloka in all_shlokas:
            shloka_has_gaps = False
            shloka_explanations = shloka.explanations.all()
            
            if not shloka_explanations.exists():
                # Shloka has no explanations - skip it
                continue
            
            # Check each explanation for this shloka
            for explanation in shloka_explanations:
                has_missing, missing_fields = self._has_missing_fields(explanation)
                if has_missing:
                    explanations_with_gaps.append((shloka, explanation, missing_fields))
                    shloka_has_gaps = True
                else:
                    explanations_complete.append(explanation)
            
            # Also check if shloka itself is missing word_by_word
            if not shloka.word_by_word:
                # Check if any explanation needs word_by_word
                for explanation in shloka_explanations:
                    has_missing, missing_fields = self._has_missing_fields(explanation)
                    if 'word_by_word' in missing_fields:
                        shloka_has_gaps = True
                        break
            
            if shloka_has_gaps:
                shlokas_with_gaps.append(shloka)
            else:
                shlokas_complete.append(shloka)
        
        # Print summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("ANALYSIS SUMMARY")
        self.stdout.write("=" * 70)
        if cleaned_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Cleaned word-by-word from {cleaned_count} explanation(s)")
            )
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created {created_count} missing explanation(s)")
            )
        if failed_creation_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠ Failed to create {failed_creation_count} explanation(s)")
            )
        self.stdout.write(f"✓ Complete shlokas (all fields filled): {len(shlokas_complete)}")
        self.stdout.write(f"✗ Shlokas with missing fields: {len(shlokas_with_gaps)}")
        self.stdout.write(f"✓ Complete explanations: {len(explanations_complete)}")
        self.stdout.write(f"✗ Explanations with missing fields: {len(explanations_with_gaps)}")
        
        if verbose and explanations_with_gaps:
            self.stdout.write("\nExplanations with missing fields:")
            for shloka, explanation, missing_fields in explanations_with_gaps[:20]:
                self.stdout.write(
                    f"  - {shloka.book_name} Ch.{shloka.chapter_number}, "
                    f"V.{shloka.verse_number} ({explanation.get_explanation_type_display()}): "
                    f"Missing: {', '.join(missing_fields)}"
                )
            if len(explanations_with_gaps) > 20:
                self.stdout.write(f"  ... and {len(explanations_with_gaps) - 20} more")
        
        self.stdout.write("=" * 70)
        
        # If we created new explanations, we need to re-analyze to check for gaps in them
        if created_count > 0 and not dry_run:
            self.stdout.write("\nRe-analyzing after creating missing explanations...")
            explanations_with_gaps = []
            explanations_complete = []
            shlokas_with_gaps = []
            shlokas_complete = []
            
            # Refresh shlokas to get newly created explanations
            for shloka in all_shlokas:
                shloka.refresh_from_db()
                shloka_has_gaps = False
                shloka_explanations = shloka.explanations.all()
                
                if not shloka_explanations.exists():
                    continue
                
                # Check each explanation for this shloka
                for explanation in shloka_explanations:
                    has_missing, missing_fields = self._has_missing_fields(explanation)
                    if has_missing:
                        explanations_with_gaps.append((shloka, explanation, missing_fields))
                        shloka_has_gaps = True
                    else:
                        explanations_complete.append(explanation)
                
                # Also check if shloka itself is missing word_by_word
                if not shloka.word_by_word:
                    # Check if any explanation needs word_by_word
                    for explanation in shloka_explanations:
                        has_missing, missing_fields = self._has_missing_fields(explanation)
                        if 'word_by_word' in missing_fields:
                            shloka_has_gaps = True
                            break
                
                if shloka_has_gaps:
                    shlokas_with_gaps.append(shloka)
                else:
                    shlokas_complete.append(shloka)
            
            if verbose:
                self.stdout.write(f"  After re-analysis: {len(explanations_with_gaps)} explanations with gaps")
        
        if not explanations_with_gaps:
            self.stdout.write(self.style.SUCCESS("\n✓ All explanations already have all fields filled!"))
            return
        
        if dry_run:
            self.stdout.write("\n" + self.style.WARNING("DRY RUN - Would fill fields in:"))
            self.stdout.write(f"  - {len(shlokas_with_gaps)} shlokas with missing fields")
            self.stdout.write(f"  - {len(explanations_with_gaps)} explanations with missing fields")
            return
        
        # Fill missing fields: iterate through each shloka, then its explanations
        total_to_fill = len(explanations_with_gaps)
        filled_count = 0
        failed_count = 0
        shlokas_processed = 0
        
        self.stdout.write(f"\nFilling missing fields...")
        self.stdout.write(f"Processing {len(shlokas_with_gaps)} shlokas with {total_to_fill} explanations needing updates")
        self.stdout.write(f"Delay between API calls: {delay}s\n")
        
        # Group explanations by shloka for better organization
        shloka_explanations_map = {}
        for shloka, explanation, missing_fields in explanations_with_gaps:
            if shloka.id not in shloka_explanations_map:
                shloka_explanations_map[shloka.id] = []
            shloka_explanations_map[shloka.id].append((explanation, missing_fields))
        
        # Process each shloka
        for shloka_idx, shloka in enumerate(shlokas_with_gaps, 1):
            if shloka.id not in shloka_explanations_map:
                continue
            
            shlokas_processed += 1
            explanations_to_process = shloka_explanations_map[shloka.id]
            
            if verbose:
                self.stdout.write(
                    f"\n[{shloka_idx}/{len(shlokas_with_gaps)}] "
                    f"Processing {shloka.book_name} Ch.{shloka.chapter_number}, V.{shloka.verse_number} "
                    f"({len(explanations_to_process)} explanation(s) to update)"
                )
            
            # Process each explanation for this shloka
            for explanation, missing_fields in explanations_to_process:
                try:
                    explanation_type = explanation.explanation_type
                    
                    if verbose:
                        self.stdout.write(
                            f"  → {explanation.get_explanation_type_display()} "
                            f"(missing: {', '.join(missing_fields)})...",
                            ending=' '
                        )
                    
                    # Generate missing fields using shloka data
                    explanation_type_str = explanation_type.lower() if hasattr(explanation_type, 'lower') else str(explanation_type).lower()
                    generated_fields = self._generate_missing_fields(shloka, missing_fields, explanation_type_str)
                    
                    # Update only the fields that were successfully generated
                    updated = False
                    update_fields = {}
                    shloka_updated = False
                    
                    for field in missing_fields:
                        if field in generated_fields and generated_fields[field]:
                            # word_by_word is saved to shloka, not explanation
                            if field == 'word_by_word':
                                shloka.word_by_word = generated_fields[field]
                                shloka_updated = True
                            else:
                                update_fields[field] = generated_fields[field]
                                updated = True
                    
                    # Save shloka if word_by_word was updated
                    if shloka_updated:
                        shloka.save(update_fields=['word_by_word', 'updated_at'])
                        updated = True
                    
                    if updated:
                        # Update the explanation with filled fields (excluding word_by_word)
                        if update_fields:
                            for field, value in update_fields.items():
                                setattr(explanation, field, value)
                            explanation.save(update_fields=list(update_fields.keys()))
                        
                        filled_count += 1
                        if verbose:
                            filled_fields = []
                            if shloka_updated:
                                filled_fields.append('word_by_word (on shloka)')
                            filled_fields.extend(update_fields.keys())
                            self.stdout.write(self.style.SUCCESS(f"✓ (filled: {', '.join(filled_fields)})"))
                    else:
                        failed_count += 1
                        if verbose:
                            self.stdout.write(self.style.WARNING("⚠ (Could not generate missing fields)"))
                    
                    # Delay to avoid rate limiting
                    time.sleep(delay)
                        
                except Exception as e:
                    failed_count += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f"✗ Error: {str(e)}"))
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ Error: {shloka.book_name} Ch.{shloka.chapter_number}, "
                                f"V.{shloka.verse_number} ({explanation_type}) - {str(e)}"
                            )
                        )
                    logger.exception(e)
                    continue
        
        # Final summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("FINAL SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(f"✓ Shlokas processed: {shlokas_processed}")
        self.stdout.write(f"✓ Successfully filled fields: {filled_count}")
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠ Could not fill: {failed_count}"))
        self.stdout.write("=" * 70)
        
        # Verify final state
        self.stdout.write("\nVerifying final state...")
        # Use the same filter as initial query
        if shloka_id:
            try:
                import uuid
                shloka_uuid = uuid.UUID(shloka_id)
                all_shlokas_after = Shloka.objects.filter(id=shloka_uuid).prefetch_related('explanations')
            except ValueError:
                all_shlokas_after = Shloka.objects.none()
        else:
            all_shlokas_after = Shloka.objects.all().prefetch_related('explanations')
        
        explanations_with_gaps_after = []
        explanations_with_word_by_word_after = []
        
        for shloka in all_shlokas_after:
            for explanation in shloka.explanations.all():
                # Check for missing fields
                has_missing, missing_fields = self._has_missing_fields(explanation)
                if has_missing:
                    explanations_with_gaps_after.append((shloka, explanation, missing_fields))
                
                # Check for word-by-word sections (should not exist)
                if explanation.explanation_text and self._has_word_by_word_section(explanation.explanation_text):
                    explanations_with_word_by_word_after.append((shloka, explanation))
        
        # Report on word-by-word sections
        if not explanations_with_word_by_word_after:
            self.stdout.write(
                self.style.SUCCESS("✓ No word-by-word sections found in explanations (clean!)")
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"\n⚠ Found {len(explanations_with_word_by_word_after)} explanation(s) still containing word-by-word sections!"
                )
            )
            if verbose:
                self.stdout.write("\nExplanations with word-by-word sections:")
                for shloka, explanation in explanations_with_word_by_word_after[:10]:
                    self.stdout.write(
                        f"  - {shloka.book_name} Ch.{shloka.chapter_number}, "
                        f"V.{shloka.verse_number} ({explanation.get_explanation_type_display()})"
                    )
                if len(explanations_with_word_by_word_after) > 10:
                    self.stdout.write(f"  ... and {len(explanations_with_word_by_word_after) - 10} more")
        
        # Report on missing fields
        if not explanations_with_gaps_after:
            self.stdout.write(self.style.SUCCESS("✓ All explanations now have all fields filled!"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ Still {len(explanations_with_gaps_after)} explanations with missing fields."
                )
            )
            if verbose:
                self.stdout.write("\nRemaining gaps:")
                for shloka, explanation, missing_fields in explanations_with_gaps_after[:10]:
                    self.stdout.write(
                        f"  - {shloka.book_name} Ch.{shloka.chapter_number}, "
                        f"V.{shloka.verse_number} ({explanation.get_explanation_type_display()}): "
                        f"Missing: {', '.join(missing_fields)}"
                    )
                if len(explanations_with_gaps_after) > 10:
                    self.stdout.write(f"  ... and {len(explanations_with_gaps_after) - 10} more")

