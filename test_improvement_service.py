#!/usr/bin/env python
"""
Test script for ImprovementService.

Tests the improvement service with a sample explanation.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.sanatan_app.models import Shloka, ShlokaExplanation
from apps.sanatan_app.services.improvement_service import ImprovementService
from apps.sanatan_app.services.quality_checker import QualityCheckerService
import uuid

def main():
    print("=" * 60)
    print("Testing Improvement Service")
    print("=" * 60)
    
    # Check if we have any explanations in the database
    explanation_count = ShlokaExplanation.objects.count()
    
    if explanation_count == 0:
        print("\n⚠ No explanations found in database.")
        print("Creating a test explanation...")
        
        # Create a test shloka if needed
        shloka, created = Shloka.objects.get_or_create(
            book_name="Bhagavad Gita",
            chapter_number=2,
            verse_number=47,
            defaults={
                'sanskrit_text': 'कर्मण्येवाधिकारस्ते मा फलेषु कदाचन',
                'transliteration': 'karmaṇy-evādhikāras te mā phaleṣhu kadāchana'
            }
        )
        
        # Create a test explanation with intentionally low quality
        explanation, created = ShlokaExplanation.objects.get_or_create(
            shloka=shloka,
            defaults={
                'summary': 'Short summary',  # Too short
                'detailed_meaning': '',  # Missing
                'detailed_explanation': 'Basic explanation',  # Too short
                'context': '',  # Missing
                'why_this_matters': '',  # Missing
                'modern_examples': [],  # Empty
                'themes': [],  # Empty
                'reflection_prompt': '',  # Missing
                'quality_score': 0,
            }
        )
        
        print(f"✓ Created test explanation (ID: {explanation.id})")
    else:
        # Use the first explanation with low quality score
        explanation = ShlokaExplanation.objects.filter(quality_score__lt=70).first()
        if not explanation:
            explanation = ShlokaExplanation.objects.first()
        print(f"\n✓ Using existing explanation (ID: {explanation.id})")
        print(f"  Shloka: {explanation.shloka}")
        print(f"  Current quality score: {explanation.quality_score}/100")
    
    # Check initial quality
    print("\n" + "-" * 60)
    print("Step 1: Checking initial quality...")
    print("-" * 60)
    
    quality_checker = QualityCheckerService()
    initial_quality = quality_checker.check_quality(explanation)
    
    print(f"Initial Quality Score: {initial_quality['overall_score']}/100")
    print(f"  - Completeness: {initial_quality['completeness_score']}/25")
    print(f"  - Clarity: {initial_quality['clarity_score']}/25")
    print(f"  - Accuracy: {initial_quality['accuracy_score']}/25")
    print(f"  - Relevance: {initial_quality['relevance_score']}/15")
    print(f"  - Structure: {initial_quality['structure_score']}/10")
    
    print("\nFeedback:")
    for metric, feedback in initial_quality['feedback'].items():
        print(f"  - {metric.capitalize()}: {feedback[:100]}...")
    
    # Test improvement service
    if initial_quality['overall_score'] < 70:
        print("\n" + "-" * 60)
        print("Step 2: Running improvement service...")
        print("-" * 60)
        
        improvement_service = ImprovementService()
        
        try:
            result = improvement_service.improve_explanation(
                explanation,
                max_iterations=2,  # Limit to 2 iterations for testing
                min_score_threshold=70
            )
            
            print(f"\n✓ Improvement completed!")
            print(f"  - Success: {result['success']}")
            print(f"  - Iterations: {result['iterations']}")
            print(f"  - Initial Score: {result['initial_score']}/100")
            print(f"  - Final Score: {result['final_score']}/100")
            print(f"  - Improvement: {result.get('improvement_delta', 0):+.1f} points")
            print(f"  - Sections Improved: {', '.join(result['improvements_made']) if result['improvements_made'] else 'None'}")
            print(f"  - Message: {result['message']}")
            
            # Refresh from database
            explanation.refresh_from_db()
            
            # Check final quality
            print("\n" + "-" * 60)
            print("Step 3: Checking final quality...")
            print("-" * 60)
            
            final_quality = quality_checker.check_quality(explanation)
            
            print(f"Final Quality Score: {final_quality['overall_score']}/100")
            print(f"  - Completeness: {final_quality['completeness_score']}/25")
            print(f"  - Clarity: {final_quality['clarity_score']}/25")
            print(f"  - Accuracy: {final_quality['accuracy_score']}/25")
            print(f"  - Relevance: {final_quality['relevance_score']}/15")
            print(f"  - Structure: {final_quality['structure_score']}/10")
            
            print(f"\n✓ Quality improved from {initial_quality['overall_score']} to {final_quality['overall_score']}!")
            
        except Exception as e:
            print(f"\n✗ Error during improvement: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"\n✓ Explanation already has high quality ({initial_quality['overall_score']}/100). Skipping improvement.")
    
    print("\n" + "=" * 60)
    print("✓ Test completed!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

