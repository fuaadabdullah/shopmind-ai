"""
Main IngestionManager class orchestrating the complete ingestion pipeline.

Coordinates fetching, processing, and indexing of vehicle manuals from
multiple sources (CHARM, ManualsLib, local directories).
"""
from typing import Any, Optional

from ..logger import setup_logger
from .document_processor import DocumentProcessor
from .fetchers import CharmFetcher, ManualslibFetcher
from .index_manager import IndexManager

logger = setup_logger(__name__)


class IngestionManager:
    """
    Main orchestrator for the ingestion pipeline.

    Combines fetching, processing, and indexing of vehicle manuals.
    """

    def __init__(self):
        """Initialize the ingestion manager with all sub-components."""
        self.doc_processor = DocumentProcessor()
        self.index_manager = IndexManager(self.doc_processor)
        self.charm_fetcher = CharmFetcher()
        self.manualslib_fetcher = ManualslibFetcher()

    def ingest_from_charm(
        self,
        make: str,
        year: str,
        model: str
    ) -> dict[str, Any]:
        """
        Complete ingestion pipeline from CHARM.

        Steps:
        1. Fetch PDF links from CHARM
        2. Download PDFs
        3. Index to FAISS

        Args:
            make: Vehicle make (e.g., "Honda")
            year: Vehicle year (e.g., "2016")
            model: Vehicle model (e.g., "Accord")

        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"Starting CHARM ingestion: {make} {year} {model}")

        print(f"\n{'='*60}")
        print(f"Starting ingestion for {make} {year} {model}")
        print(f"{'='*60}\n")

        results = {
            "make": make,
            "year": year,
            "model": model,
            "pdf_links_found": 0,
            "pdfs_downloaded": 0,
            "pdfs_indexed": 0,
            "pdfs_skipped": 0,
            "errors": []
        }

        try:
            # Step 1: Fetch and download from CHARM
            fetch_result = self.charm_fetcher.fetch_and_download(make, year, model)
            results["pdf_links_found"] = fetch_result["links_found"]
            results["pdfs_downloaded"] = len(fetch_result["downloads"])

            if not fetch_result["downloads"]:
                logger.info("No PDFs downloaded")
                return results

            # Step 2: Index downloaded PDFs
            print(f"\n[3/4] Indexing PDFs to FAISS...")
            metadata = {
                "make": make,
                "year": year,
                "model": model,
                "source": "CHARM"
            }

            index_results = self.index_manager.index_multiple_pdfs(
                fetch_result["downloads"],
                metadata
            )

            results["pdfs_indexed"] = index_results["success"]
            results["pdfs_skipped"] = index_results["skipped"]

            # Print summary
            print(f"\n[4/4] Complete!")
            print(f"  - Links found: {results['pdf_links_found']}")
            print(f"  - Downloaded: {results['pdfs_downloaded']}")
            print(f"  - Indexed: {results['pdfs_indexed']}")
            print(f"  - Skipped: {results['pdfs_skipped']}")

            logger.info(f"CHARM ingestion complete: {results}")
            return results

        except Exception as e:
            logger.error(f"CHARM ingestion failed: {str(e)}", exc_info=True)
            results["errors"].append(f"Ingestion error: {str(e)}")
            return results

    def search_manualslib(self, query: str) -> dict[str, Any]:
        """
        Search ManualsLib for manuals.

        Args:
            query: Search query (e.g., "Honda Accord 2016 service manual")

        Returns:
            Dictionary with search results
        """
        logger.info(f"Searching ManualsLib: {query}")

        print(f"\n{'='*60}")
        print(f"Searching ManualsLib: {query}")
        print(f"{'='*60}\n")

        try:
            result = self.manualslib_fetcher.search(query)

            print(f"Found {result['manuals_found']} manuals:")
            for url in result["urls"][:5]:  # Show first 5
                print(f"  - {url}")

            logger.info(f"ManualsLib search complete: {result}")
            return result

        except Exception as e:
            logger.error(f"ManualsLib search failed: {str(e)}", exc_info=True)
            return {
                "query": query,
                "manuals_found": 0,
                "urls": [],
                "error": str(e)
            }

    def ingest_from_directory(
        self,
        directory_path: str,
        make: str,
        year: str,
        model: str
    ) -> dict[str, Any]:
        """
        Ingest all PDFs from a local directory.

        Args:
            directory_path: Path to directory containing PDFs
            make: Vehicle make
            year: Vehicle year
            model: Vehicle model

        Returns:
            Dictionary with ingestion results
        """
        logger.info(f"Indexing directory: {directory_path}")

        print(f"\n{'='*60}")
        print(f"Indexing PDFs from directory: {directory_path}")
        print(f"{'='*60}\n")

        try:
            metadata = {
                "make": make,
                "year": year,
                "model": model,
                "source": "local_directory"
            }

            results = self.index_manager.index_directory(directory_path, metadata)

            print(f"\nIndexing complete:")
            print(f"  - Success: {results['success']}")
            print(f"  - Skipped: {results['skipped']}")
            print(f"  - Failed: {results['failed']}")

            logger.info(f"Directory ingestion complete: {results}")
            return results

        except Exception as e:
            logger.error(f"Directory ingestion failed: {str(e)}", exc_info=True)
            return {
                "directory": directory_path,
                "success": 0,
                "skipped": 0,
                "failed": 0,
                "error": str(e)
            }

    def batch_ingest_from_charm(
        self,
        vehicles: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """
        Batch ingest from CHARM for multiple vehicles.

        Args:
            vehicles: List of dicts with make, year, model keys

        Returns:
            List of ingestion results
        """
        logger.info(f"Starting batch ingestion for {len(vehicles)} vehicles")

        print(f"\n{'#'*60}")
        print(f"# Starting batch ingestion for {len(vehicles)} vehicles")
        print(f"{'#'*60}\n")

        all_results = []

        for i, vehicle in enumerate(vehicles, 1):
            make = vehicle.get("make")
            year = vehicle.get("year")
            model = vehicle.get("model")

            print(f"\n[{i}/{len(vehicles)}] Processing {make} {year} {model}...")

            result = self.ingest_from_charm(make, year, model)
            all_results.append(result)

        # Print summary
        print(f"\n{'#'*60}")
        print(f"# BATCH INGESTION COMPLETE")
        print(f"{'#'*60}")

        total_indexed = sum(
            r.get("pdfs_indexed", 0) for r in all_results
        )
        total_downloaded = sum(
            r.get("pdfs_downloaded", 0) for r in all_results
        )
        total_links = sum(
            r.get("pdf_links_found", 0) for r in all_results
        )

        print(f"Total PDFs found: {total_links}")
        print(f"Total PDFs downloaded: {total_downloaded}")
        print(f"Total PDFs indexed: {total_indexed}")

        logger.info(
            f"Batch ingestion complete: "
            f"{total_links} found, {total_downloaded} downloaded, {total_indexed} indexed"
        )

        return all_results
