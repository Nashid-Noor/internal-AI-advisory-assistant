#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25 import get_bm25_index

setup_logging()
logger = get_logger(__name__)

def init_db(reset=False):
    # Directories
    dirs = [
        Path(settings.data_raw_path),
        Path(settings.data_processed_path),
        Path(settings.qdrant_path),
        Path(settings.feedback_db_path).parent,
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Vector Store
    logger.info("Initializing vector store...")
    vector_store = get_vector_store()
    
    if reset:
        try:
            vector_store.clear_collection()
            logger.warning("Vector store cleared")
        except Exception:
            pass
    
    vector_store.initialize()
    
    # BM25
    logger.info("Initializing BM25...")
    bm25 = get_bm25_index()
    if reset:
        bm25.clear()

    # Done
    print("\n" + "="*50)
    print("DB Init Complete")
    print("="*50)
    print(f"Vector DB: {settings.qdrant_path}")
    print(f"Raw Data:  {settings.data_raw_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset all data")
    args = parser.parse_args()
    
    if args.reset:
        if input("Reset all data? (y/n): ").lower() != 'y':
            sys.exit(0)
            
    init_db(args.reset)
