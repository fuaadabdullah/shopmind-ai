#!/usr/bin/env python3
"""Quick verification script for Alembic setup."""
import subprocess
import os
import sqlite3
from pathlib import Path

def main():
    """Verify Alembic setup."""
    print("🔍 Verifying Alembic Setup\n")
    
    # Check alembic.ini exists
    if Path("alembic.ini").exists():
        print("✅ alembic.ini exists")
    else:
        print("❌ alembic.ini not found")
        return
    
    # Check alembic directory exists
    if Path("alembic").is_dir():
        print("✅ alembic/ directory exists")
    else:
        print("❌ alembic/ directory not found")
        return
    
    # Check migration files exist
    versions_dir = Path("alembic/versions")
    migration_files = list(versions_dir.glob("*.py"))
    if migration_files:
        print(f"✅ {len(migration_files)} migration file(s) found:")
        for mf in sorted(migration_files):
            print(f"   - {mf.name}")
    else:
        print("❌ No migration files found")
        return
    
    # Check database was created by migration
    db_path = Path("data/shopmind.db")
    if db_path.exists():
        print(f"✅ Database exists at {db_path}")
        
        # Verify tables
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = [row[0] for row in cursor.fetchall()]
            
            if tables:
                print(f"✅ {len(tables)} tables found:")
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table});")
                    columns = [row[1] for row in cursor.fetchall()]
                    print(f"   - {table}: {', '.join(columns[:3])}{'...' if len(columns) > 3 else ''}")
                
                # Verify critical columns
                if 'diagnostic_sessions' in tables:
                    cursor.execute("PRAGMA table_info(diagnostic_sessions);")
                    columns = {row[1] for row in cursor.fetchall()}
                    
                    critical_cols = {'torch_predictions', 'predicted_causes', 'training_ready', 'confirmed_cause'}
                    missing = critical_cols - columns
                    if not missing:
                        print("✅ All Torch ML fields present in diagnostic_sessions")
                    else:
                        print(f"❌ Missing columns: {missing}")
            
            conn.close()
        except Exception as e:
            print(f"❌ Error checking database: {e}")
    else:
        print(f"❌ Database not found at {db_path}")
    
    # Check Alembic version
    print("\n📦 Alembic Status:")
    result = subprocess.run(["alembic", "current"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ Alembic commands work")
        for line in result.stdout.strip().split('\n'):
            if 'fada02c1d3ab' in line or 'Current revision' in line:
                print(f"   {line}")
    
    print("\n✅ Alembic setup verification complete!")

if __name__ == "__main__":
    main()
