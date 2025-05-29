import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from data.ingestion.data_loader import DataLoader
from data.processing.cleaner import DataCleaner


# Usage example
if __name__ == "__main__":
    # Example usage
    loader = DataLoader(
        file_path=next(Path("../data/").rglob("*.pdf")),
        filetype=".pdf",
        recursive=True,
        max_workers=4,
    )
    
    documents = loader.load()
    logger = logging.getLogger()

    cleaner = DataCleaner(logger)
    documents = cleaner.clean_documents(documents)
    print(documents)
