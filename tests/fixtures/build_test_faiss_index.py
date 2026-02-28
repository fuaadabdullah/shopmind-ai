"""Build FAISS test index with real embeddings for E2E tests.

This script generates a test FAISS index using real SentenceTransformer
embeddings of synthetic automotive diagnostic scenarios.
"""
import os
import pickle
import sys
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.fixtures.generate_test_data import get_test_diagnostic_scenarios
from app.logger import setup_logger

logger = setup_logger(__name__)

# Configuration
TEST_INDEX_DIR = Path(__file__).parent / "test_faiss_index"
INDEX_PATH = TEST_INDEX_DIR / "index.bin"
META_PATH = TEST_INDEX_DIR / "meta.pkl"
DIMENSION = 384
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def build_test_faiss_index(force_rebuild: bool = False) -> None:
    """Build FAISS index from test diagnostic scenarios.
    
    Args:
        force_rebuild: If True, rebuild even if index exists
    """
    # Check if index already exists
    if INDEX_PATH.exists() and META_PATH.exists() and not force_rebuild:
        logger.info(f"Test FAISS index already exists at {TEST_INDEX_DIR}")
        with open(META_PATH, "rb") as f:
            metadata = pickle.load(f)
        logger.info(f"Existing index contains {len(metadata)} documents")
        return
    
    logger.info("Building test FAISS index...")
    
    # Create output directory
    TEST_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load test scenarios
    scenarios = get_test_diagnostic_scenarios()
    logger.info(f"Loaded {len(scenarios)} test diagnostic scenarios")
    
    # Initialize embedding model
    logger.info(f"Loading SentenceTransformer model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    
    # Prepare texts for embedding
    # Combine cause, description, symptoms, and OBD codes for better retrieval
    texts = []
    metadata = []
    
    for scenario in scenarios:
        # Create rich text for embedding
        symptoms_text = " ".join(scenario["symptoms"])
        obd_texts = " ".join(scenario["obd_codes"])
        
        text = (
            f"{scenario['cause']}. "
            f"{scenario['description']} "
            f"Symptoms: {symptoms_text}. "
            f"OBD Codes: {obd_texts}."
        )
        texts.append(text)
        
        # Store metadata (exclude symptoms/obd_codes used only for embedding)
        metadata.append({
            "cause": scenario["cause"],
            "description": scenario["description"],
            "tests": scenario["tests"],
            "labor_hours": scenario["labor_hours"]
        })
    
    # Generate embeddings
    logger.info("Generating embeddings for test documents...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    logger.info(f"Generated {embeddings.shape[0]} embeddings of dimension {embeddings.shape[1]}")
    
    # Normalize embeddings for cosine similarity (IndexFlatIP expects normalized vectors)
    faiss.normalize_L2(embeddings)
    
    # Create FAISS index
    logger.info("Creating FAISS index...")
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(embeddings.astype(np.float32))
    
    # Save index
    logger.info(f"Saving FAISS index to {INDEX_PATH}")
    faiss.write_index(index, str(INDEX_PATH))
    
    # Save metadata
    logger.info(f"Saving metadata to {META_PATH}")
    with open(META_PATH, "wb") as f:
        pickle.dump(metadata, f)
    
    logger.info(f"✅ Test FAISS index built successfully!")
    logger.info(f"   - Index: {INDEX_PATH}")
    logger.info(f"   - Metadata: {META_PATH}")
    logger.info(f"   - Documents: {len(metadata)}")
    logger.info(f"   - Dimension: {DIMENSION}")


def verify_test_index() -> None:
    """Verify the test index can be loaded and searched."""
    if not INDEX_PATH.exists() or not META_PATH.exists():
        logger.error("Test index does not exist. Run build_test_faiss_index() first.")
        return
    
    logger.info("Verifying test FAISS index...")
    
    # Load index
    index = faiss.read_index(str(INDEX_PATH))
    with open(META_PATH, "rb") as f:
        metadata = pickle.load(f)
    
    logger.info(f"✅ Index loaded: {index.ntotal} vectors")
    logger.info(f"✅ Metadata loaded: {len(metadata)} documents")
    
    # Test search with a sample query
    model = SentenceTransformer(MODEL_NAME)
    query = "car won't start and makes clicking sound"
    query_embedding = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)
    
    # Search
    k = 3
    distances, indices = index.search(query_embedding.astype(np.float32), k)
    
    logger.info(f"\n🔍 Test search query: '{query}'")
    logger.info(f"Top {k} results:")
    for i, (idx, score) in enumerate(zip(indices[0], distances[0]), 1):
        doc = metadata[idx]
        logger.info(f"  {i}. {doc['cause']} (score: {score:.4f})")
        logger.info(f"     {doc['description'][:100]}...")
    
    logger.info("\n✅ Test index verification complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build test FAISS index")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild even if index exists")
    parser.add_argument("--verify", action="store_true", help="Verify index after building")
    args = parser.parse_args()
    
    build_test_faiss_index(force_rebuild=args.rebuild)
    
    if args.verify:
        verify_test_index()
