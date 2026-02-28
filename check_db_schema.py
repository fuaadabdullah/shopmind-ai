#!/usr/bin/env python3
"""Verify database schema created by Alembic migrations."""
import sqlite3
from pathlib import Path

def main():
    """Verify database schema."""
    db_path = Path("data/shopmind.db")
    
    if not db_path.exists():
        print("❌ Database file not found")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("📊 Database Schema Verification\n")
    print(f"✅ Database: {db_path}")
    print(f"✅ Tables: {', '.join(tables)}\n")
    
    # Check diagnostic_sessions
    print("📍 diagnostic_sessions table:")
    cursor.execute("PRAGMA table_info(diagnostic_sessions);")
    columns = cursor.fetchall()
    torch_cols = {'torch_predictions', 'predicted_causes', 'training_ready', 'confirmed_cause'}
    found_torch = set()
    
    for col_id, name, col_type, notnull, dflt, pk in columns:
        marker = "⭐" if name in torch_cols else "  "
        print(f"{marker} {name}: {col_type}")
        if name in torch_cols:
            found_torch.add(name)
    
    # Check indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='diagnostic_sessions';")
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"\n✅ Indexes: {len(indexes)} created on diagnostic_sessions")
    
    # Check root_causes
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='root_causes';")
    if cursor.fetchone()[0]:
        print("✅ root_causes table: present")
    
    # Check alembic_version
    cursor.execute("SELECT version_num FROM alembic_version;")
    version = cursor.fetchone()
    print(f"\n✅ Migration Status: {version[0] if version else 'None'}")
    
    # Verify Torch fields
    missing_torch = torch_cols - found_torch
    if not missing_torch:
        print("✅ All Torch ML fields present!")
    else:
        print(f"❌ Missing Torch fields: {missing_torch}")
    
    conn.close()
    print("\n✅ Database schema verification complete!")

if __name__ == "__main__":
    main()
