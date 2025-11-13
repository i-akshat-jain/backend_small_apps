#!/usr/bin/env python3
"""Migration script to create database tables from SQLAlchemy models."""
import sys
import logging
from sqlalchemy import inspect, text
from database import engine, init_db, SessionLocal
from models import (
    Base,
    ShlokaORM,
    ShlokaExplanationORM,
    UserORM,
    ReadingLogORM
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_existing_tables():
    """Get list of existing tables in the database."""
    inspector = inspect(engine)
    return inspector.get_table_names()


def check_table_exists(table_name):
    """Check if a specific table exists."""
    existing_tables = get_existing_tables()
    return table_name in existing_tables


def show_table_structure(table_name):
    """Show the structure of an existing table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return None
    
    columns = inspector.get_columns(table_name)
    return columns


def migrate():
    """Create all tables defined in models."""
    print("=" * 60)
    print("DATABASE MIGRATION - Creating Tables")
    print("=" * 60)
    
    # Get existing tables before migration
    existing_tables_before = get_existing_tables()
    print(f"\nExisting tables before migration: {len(existing_tables_before)}")
    if existing_tables_before:
        print(f"  {', '.join(existing_tables_before)}")
    
    # Define expected tables from models
    expected_tables = [
        "shlokas",
        "shloka_explanations",
        "users",
        "reading_logs"
    ]
    
    print(f"\nExpected tables from models:")
    for table in expected_tables:
        exists = check_table_exists(table)
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"  {table}: {status}")
    
    # Check for conflicts with existing tables
    conflicting_tables = []
    for table in expected_tables:
        if table in existing_tables_before:
            conflicting_tables.append(table)
    
    if conflicting_tables:
        print(f"\n⚠ WARNING: The following tables already exist:")
        for table in conflicting_tables:
            print(f"  - {table}")
        print("\n  SQLAlchemy will NOT overwrite existing tables.")
        print("  If you need to recreate them, drop them first manually.")
    
    # Create tables
    print(f"\n{'=' * 60}")
    print("Creating tables...")
    print("=" * 60)
    
    try:
        # Import all models to ensure they're registered
        # This ensures all tables are included in metadata
        init_db()
        
        # Get tables after migration
        existing_tables_after = get_existing_tables()
        print(f"\n✓ Migration completed!")
        print(f"\nTables after migration: {len(existing_tables_after)}")
        
        # Show newly created tables
        new_tables = set(existing_tables_after) - set(existing_tables_before)
        if new_tables:
            print(f"\n✓ Newly created tables ({len(new_tables)}):")
            for table in sorted(new_tables):
                print(f"  - {table}")
        else:
            print("\n  No new tables created (all tables already existed)")
        
        # Verify expected tables exist
        print(f"\n{'=' * 60}")
        print("Verification")
        print("=" * 60)
        
        all_exist = True
        for table in expected_tables:
            exists = check_table_exists(table)
            status = "✓" if exists else "✗"
            print(f"  {status} {table}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print(f"\n✓ All expected tables exist!")
        else:
            print(f"\n✗ Some expected tables are missing!")
            return False
        
        # Show table structures
        print(f"\n{'=' * 60}")
        print("Table Structures")
        print("=" * 60)
        
        for table_name in expected_tables:
            if check_table_exists(table_name):
                columns = show_table_structure(table_name)
                if columns:
                    print(f"\n{table_name}:")
                    for col in columns:
                        nullable = "NULL" if col['nullable'] else "NOT NULL"
                        default = f" DEFAULT {col['default']}" if col.get('default') else ""
                        print(f"  - {col['name']}: {col['type']} {nullable}{default}")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print(f"\n✗ Migration failed: {e}")
        return False


def show_table_info():
    """Show information about all tables in the database."""
    print("\n" + "=" * 60)
    print("ALL TABLES IN DATABASE")
    print("=" * 60)
    
    existing_tables = get_existing_tables()
    print(f"\nTotal tables: {len(existing_tables)}")
    
    if existing_tables:
        for table in sorted(existing_tables):
            print(f"\n{table}:")
            columns = show_table_structure(table)
            if columns:
                for col in columns:
                    nullable = "NULL" if col['nullable'] else "NOT NULL"
                    print(f"  - {col['name']}: {col['type']} {nullable}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("=" * 60)
    
    # Show current state
    show_table_info()
    
    # Run migration
    success = migrate()
    
    # Show final state
    show_table_info()
    
    if success:
        print("\n" + "=" * 60)
        print("✓ MIGRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ MIGRATION FAILED")
        print("=" * 60)
        sys.exit(1)

