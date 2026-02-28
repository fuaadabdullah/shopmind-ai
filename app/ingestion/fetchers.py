"""
Fetcher classes for retrieving manuals from various sources.

CharmFetcher: Fetches from Operation CHARM
ManualslibFetcher: Searches and retrieves from ManualsLib
"""
import os
from typing import Any

from ..logger import setup_logger
from .fetch_charm import download_pdf, fetch_charm_manuals
from .fetch_manualslib import search_manualslib

logger = setup_logger(__name__)


class CharmFetcher:
    """Fetches vehicle manuals from Operation CHARM."""

    BASE_URL = "https://charm.li"

    def __init__(self, save_dir: str = "data/manuals") -> None:
        """
        Initialize CHARM fetcher.

        Args:
            save_dir: Base directory for saving downloaded PDFs
        """
        self.save_dir = save_dir

    def fetch_and_download(
        self,
        make: str,
        year: str,
        model: str
    ) -> dict[str, Any]:
        """
        Fetch PDF links and download them.

        Args:
            make: Vehicle make (e.g., "Honda")
            year: Vehicle year (e.g., "2016")
            model: Vehicle model (e.g., "Accord")

        Returns:
            Dictionary with results (links_found, downloaded_paths, errors)
        """
        logger.info(f"Fetching CHARM manuals: {make} {year} {model}")

        result = {
            "make": make,
            "year": year,
            "model": model,
            "links_found": 0,
            "downloads": []
        }

        try:
            # Fetch PDF links from CHARM
            logger.info("[1/2] Fetching PDF links from CHARM...")
            links = fetch_charm_manuals(make, year, model)
            result["links_found"] = len(links)

            if not links:
                logger.warning("No PDF links found on CHARM")
                return result

            logger.info(f"Found {len(links)} PDF links")

            # Download PDFs
            logger.info("[2/2] Downloading PDFs...")
            download_dir = f"{self.save_dir}/{make}/{year}/{model}"
            os.makedirs(download_dir, exist_ok=True)

            for link in links:
                try:
                    path = download_pdf(link, download_dir)
                    if path:
                        result["downloads"].append(path)
                        logger.info(f"Downloaded: {path}")
                except Exception as e:
                    logger.warning(f"Failed to download {link}: {str(e)}")

            logger.info(
                f"CHARM ingestion complete: "
                f"{result['links_found']} found, {len(result['downloads'])} downloaded"
            )

            return result

        except Exception as e:
            logger.error(f"CHARM fetching failed: {str(e)}", exc_info=True)
            raise


class ManualslibFetcher:
    """Searches and retrieves information from ManualsLib."""

    def __init__(self) -> None:
        """Initialize ManualsLib fetcher."""
        pass

    def search(self, query: str) -> dict[str, Any]:
        """
        Search ManualsLib for manuals.

        Args:
            query: Search query (e.g., "Honda Accord 2016 service manual")

        Returns:
            Dictionary with search results (urls, manuals_found)
        """
        logger.info(f"Searching ManualsLib: {query}")

        result = {
            "query": query,
            "manuals_found": 0,
            "urls": []
        }

        try:
            logger.info("Performing ManualsLib search...")
            urls = search_manualslib(query)
            result["manuals_found"] = len(urls)
            result["urls"] = urls

            if urls:
                logger.info(f"Found {len(urls)} manuals")
                for url in urls[:3]:  # Log first 3
                    logger.debug(f"  - {url}")
            else:
                logger.warning("No manuals found")

            return result

        except Exception as e:
            logger.error(f"ManualsLib search failed: {str(e)}", exc_info=True)
            raise
