"""
Script to add sample shlokas to the database.
Run this after setting up your .env file and database schema.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import ShlokaORM
from uuid import uuid4

# Sample Bhagavad Gita shlokas
SAMPLE_SHLOKAS = [
    {
        "book_name": "Bhagavad Gita",
        "chapter_number": 2,
        "verse_number": 47,
        "sanskrit_text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
        "transliteration": "karmaṇy-evādhikāras te mā phaleṣhu kadāchana\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi"
    },
    {
        "book_name": "Bhagavad Gita",
        "chapter_number": 2,
        "verse_number": 20,
        "sanskrit_text": "न जायते म्रियते वा कदाचिन्नायं भूत्वा भविता वा न भूयः। अजो नित्यः शाश्वतोऽयं पुराणो न हन्यते हन्यमाने शरीरे॥",
        "transliteration": "na jāyate mriyate vā kadāchin\nnāyaṁ bhūtvā bhavitā vā na bhūyaḥ\najo nityaḥ śhāśhvato 'yaṁ purāṇo\nna hanyate hanyamāne śharīre"
    },
    {
        "book_name": "Bhagavad Gita",
        "chapter_number": 6,
        "verse_number": 5,
        "sanskrit_text": "उद्धरेदात्मनात्मानं नात्मानमवसादयेत्। आत्मैव ह्यात्मनो बन्धुरात्मैव रिपुरात्मनः॥",
        "transliteration": "uddhared ātmanātmānaṁ nātmānam avasādayet\nātmaiva hy ātmano bandhur ātmaiva ripur ātmanaḥ"
    },
    {
        "book_name": "Bhagavad Gita",
        "chapter_number": 3,
        "verse_number": 19,
        "sanskrit_text": "तस्मादसक्तः सततं कार्यं कर्म समाचर। असक्तो ह्याचरन्कर्म परमाप्नोति पूरुषः॥",
        "transliteration": "tasmād asaktaḥ satataṁ kāryaṁ karma samāchara\nasakto hy ācharan karma param āpnoti pūruṣhaḥ"
    },
    {
        "book_name": "Bhagavad Gita",
        "chapter_number": 2,
        "verse_number": 62,
        "sanskrit_text": "ध्यायतो विषयान्पुंसः सङ्गस्तेषूपजायते। सङ्गात्सञ्जायते कामः कामात्क्रोधोऽभिजायते॥",
        "transliteration": "dhyāyato viṣhayān puṁsaḥ saṅgas teṣhūpajāyate\nsaṅgāt sañjāyate kāmaḥ kāmāt krodho 'bhijāyate"
    },
]


def add_shlokas():
    """Add sample shlokas to the database."""
    db = SessionLocal()
    
    try:
        print("Adding sample shlokas to database...")
        
        for shloka_data in SAMPLE_SHLOKAS:
            try:
                # Check if shloka already exists
                existing = db.query(ShlokaORM).filter(
                    ShlokaORM.book_name == shloka_data["book_name"],
                    ShlokaORM.chapter_number == shloka_data["chapter_number"],
                    ShlokaORM.verse_number == shloka_data["verse_number"]
                ).first()
                
                if existing:
                    print(
                        f"Shloka {shloka_data['book_name']} "
                        f"Chapter {shloka_data['chapter_number']}, "
                        f"Verse {shloka_data['verse_number']} already exists. Skipping."
                    )
                    continue
                
                # Create new shloka
                shloka = ShlokaORM(
                    id=uuid4(),
                    book_name=shloka_data["book_name"],
                    chapter_number=shloka_data["chapter_number"],
                    verse_number=shloka_data["verse_number"],
                    sanskrit_text=shloka_data["sanskrit_text"],
                    transliteration=shloka_data.get("transliteration")
                )
                
                db.add(shloka)
                db.commit()
                
                print(
                    f"✓ Added: {shloka_data['book_name']} "
                    f"Chapter {shloka_data['chapter_number']}, "
                    f"Verse {shloka_data['verse_number']} (ID: {shloka.id})"
                )
            except Exception as e:
                db.rollback()
                print(f"✗ Error adding shloka {shloka_data['book_name']} "
                      f"Chapter {shloka_data['chapter_number']}, "
                      f"Verse {shloka_data['verse_number']}: {str(e)}")
        
        print("\nDone!")
    except Exception as e:
        db.rollback()
        print(f"Error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    add_shlokas()

