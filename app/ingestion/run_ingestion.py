"""
Run Ingestion - Command-line interface for the ingestion pipeline.

Entry point for fetching, processing, and indexing vehicle manuals.
Uses the class-based IngestionManager.

Examples:
    # Ingest from CHARM
    python run_ingestion.py --source charm --make Honda --year 2016 --model Accord

    # Search ManualsLib
    python run_ingestion.py --source manualslib --query "Honda Accord 2016"

    # Index local directory
    python run_ingestion.py --source dir --directory ./manuals --make Honda --year 2016 --model Accord

    # Batch ingestion
    python run_ingestion.py --source batch
"""
import argparse
import sys

from .ingestion_manager import IngestionManager

# Priority list of makes/models for batch ingestion
DEFAULT_PRIORITY_LIST = [
    {"make": "Honda", "year": "2016", "model": "Accord"},
    {"make": "Toyota", "year": "2016", "model": "Camry"},
    {"make": "Ford", "year": "2016", "model": "F-150"},
    {"make": "Chevrolet", "year": "2016", "model": "Silverado"},
    {"make": "BMW", "year": "2016", "model": "3 Series"},
    {"make": "Mercedes", "year": "2016", "model": "C-Class"},
    {"make": "Audi", "year": "2016", "model": "A4"},
    {"make": "Nissan", "year": "2016", "model": "Altima"},
    {"make": "Hyundai", "year": "2016", "model": "Elantra"},
    {"make": "Kia", "year": "2016", "model": "Optima"},
]


def run():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="ShopMindAI Manual Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--source",
        choices=["charm", "manualslib", "dir", "batch"],
        default="charm",
        help="Source for ingestion (default: charm)"
    )
    parser.add_argument(
        "--make",
        type=str,
        help="Vehicle make (required for charm and dir sources)"
    )
    parser.add_argument(
        "--year",
        type=str,
        help="Vehicle year (required for charm and dir sources)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Vehicle model (required for charm and dir sources)"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Search query (required for manualslib source)"
    )
    parser.add_argument(
        "--directory",
        type=str,
        help="Directory path (required for dir source)"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch ingestion"
    )

    args = parser.parse_args()

    # Create ingestion manager
    manager = IngestionManager()

    # Route to appropriate ingestion method
    if args.source == "charm":
        if not args.make or not args.year or not args.model:
            print("Error: --make, --year, and --model required for CHARM source")
            print("Example: python -m app.ingestion.run_ingestion --source charm --make Honda --year 2016 --model Accord")
            sys.exit(1)

        manager.ingest_from_charm(args.make, args.year, args.model)

    elif args.source == "manualslib":
        if not args.query:
            print("Error: --query required for ManualsLib source")
            print('Example: python -m app.ingestion.run_ingestion --source manualslib --query "Honda Accord 2016"')
            sys.exit(1)

        manager.search_manualslib(args.query)

    elif args.source == "dir":
        if not args.directory or not args.make or not args.year or not args.model:
            print("Error: --directory, --make, --year, and --model required for dir source")
            print("Example: python -m app.ingestion.run_ingestion --source dir --directory ./manuals --make Honda --year 2016 --model Accord")
            sys.exit(1)

        manager.ingest_from_directory(args.directory, args.make, args.year, args.model)

    elif args.source == "batch" or args.batch:
        manager.batch_ingest_from_charm(DEFAULT_PRIORITY_LIST)


if __name__ == "__main__":
    run()

