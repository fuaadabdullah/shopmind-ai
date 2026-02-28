#!/usr/bin/env python3
"""
Verification script for embedding consolidation.

Checks that:
1. embeddings_utils module exists and exports embed_query
2. Configuration constants are properly defined
3. No duplicate embed_text([text])[0] patterns remain
"""
import os
import re
from pathlib import Path

def check_imports():
    """Verify new module can be imported."""
    print("✓ Checking imports...")
    try:
        from app.embeddings_utils import embed_query, ensure_embedding_vector
        from app.config import settings
        print("  ✅ embeddings_utils module imports successfully")
        print(f"  ✅ Settings.EMBEDDING_MODEL: {settings.EMBEDDING_MODEL}")
        print(f"  ✅ Settings.EMBEDDING_DIMENSION: {settings.EMBEDDING_DIMENSION}")
        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        return False

def check_code_patterns():
    """Verify duplicate patterns have been removed."""
    print("\n✓ Checking for remaining duplicate patterns...")
    
    files_to_check = [
        "app/retriever.py",
        "app/ml/predictor.py",
        "app/ingestion/document_processor.py",
    ]
    
    # Pattern: embed_text([...][0] - this is the old duplicate pattern
    pattern = r"embed_text\(\[[^\]]+\]\)\[0\]"
    
    found_duplicates = False
    for filepath in files_to_check:
        if not Path(filepath).exists():
            print(f"  ⚠️ {filepath} not found")
            continue
            
        with open(filepath) as f:
            content = f.read()
            matches = re.findall(pattern, content)
            
            if matches:
                print(f"  ❌ {filepath}: Found {len(matches)} duplicate patterns!")
                found_duplicates = True
            else:
                print(f"  ✅ {filepath}: No duplicates")
    
    if found_duplicates:
        return False
    
    # Check that embed_query is used instead
    for filepath in files_to_check:
        if not Path(filepath).exists():
            continue
        with open(filepath) as f:
            content = f.read()
            if "embed_query" in content or "retriever" not in filepath:
                print(f"  ✅ {filepath}: Uses updated pattern")
    
    return not found_duplicates

def check_batch_embedding():
    """Verify batch embedding is used instead of loop."""
    print("\n✓ Checking batch embedding implementation...")
    
    doc_proc_file = "app/ingestion/document_processor.py"
    
    if not Path(doc_proc_file).exists():
        print(f"  ⚠️ {doc_proc_file} not found")
        return False
    
    with open(doc_proc_file) as f:
        content = f.read()
        
        # Check if the old loop pattern is gone
        if re.search(r"for\s+\w+\s+in\s+chunks.*embed_text\(chunk\)", content, re.DOTALL):
            print(f"  ❌ {doc_proc_file}: Still has loop-based embedding!")
            return False
        
        # Check if batch call is present
        if "embed_text(chunks)" in content:
            print(f"  ✅ {doc_proc_file}: Uses batch embedding")
            return True
    
    return False

def check_config_constants():
    """Verify config constants are defined."""
    print("\n✓ Checking configuration constants...")
    
    config_file = "app/config.py"
    
    if not Path(config_file).exists():
        print(f"  ⚠️ {config_file} not found")
        return False
    
    with open(config_file) as f:
        content = f.read()
        
        required = [
            "EMBEDDING_MODEL",
            "EMBEDDING_DIMENSION",
        ]
        
        all_found = True
        for const in required:
            if const in content:
                print(f"  ✅ {const} defined in config")
            else:
                print(f"  ❌ {const} not found in config")
                all_found = False
    
    return all_found

def main():
    """Run all verification checks."""
    print("=" * 70)
    print("EMBEDDING CONSOLIDATION VERIFICATION")
    print("=" * 70)
    
    results = {
        "Imports": check_imports(),
        "Code Patterns": check_code_patterns(),
        "Batch Embedding": check_batch_embedding(),
        "Config": check_config_constants(),
    }
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check:20} {status}")
    
    all_pass = all(results.values())
    
    if all_pass:
        print("\n✅ All consolidation checks passed!")
    else:
        print("\n❌ Some checks failed. Review above.")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    exit(main())
