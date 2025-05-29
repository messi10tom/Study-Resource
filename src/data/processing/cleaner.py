from abc import ABC, abstractmethod
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import logging
from typing import Any, Dict, Optional, List

from langchain_core.documents.base import Document

# Custom error for cleaner
class CleanerError(Exception):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}

class BaseCleaningOperation(ABC):
    """Abstract Base Class for cleaning operations"""

    @abstractmethod
    def apply(self, text: str) -> str:
        """Appy cleaning operation to text"""
        pass

class WhitespaceNormalizer(BaseCleaningOperation):
    """Normalize whitespaces"""
    def __init__(self, preserve_para: bool = True):
        self.preserve_para = preserve_para

    def apply(self, text: str) -> str:
        if self.preserve_para:
            # Replaces multiple spaces/tabs with ' '
            # Preserve line breaks
            # Replaces multiple newlines with double line break(paragraph)
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        else:
            # Replace all whitespace with single spaces
            text = re.sub(r'\s+', ' ', text)

        return text.strip()

class DataCleaner:
    """
    Data cleaner for the document processing pipeline
    """
    def __init__(self,
                 logger: logging.Logger,
                 operations: Optional[List[BaseCleaningOperation]] = None,
                 max_workers: int = 4,
                 preserve_metadata: bool = True,
                 ):

        self.operations = operations or self._default_operations()
        self.max_workers = max_workers
        self.logger = logger
        self.preserve_metadata = preserve_metadata

        self._errors = []
        # Validate operations
        self._validate_operations()

    # Validate the operations
    def _validate_operations(self) -> None:
        if not self.operations:
            raise CleanerError("No cleaning operations provided")

        for op in self.operations:
            if not isinstance(op, BaseCleaningOperation):
                raise CleanerError(f"Invalid cleaning operation type: {type(op)}")

    def _default_operations(self) -> List[BaseCleaningOperation]:
        """Get default cleaning operations"""
        return [
                WhitespaceNormalizer()
                ]

    def _clean_single_document(self, document: Document) -> Document:
        try:
            original_text = document.page_content
            original_length = len(original_text)

            # TODO: UTF validation requires
            cleaned_text = ""

            # Applying cleaning operation sequentially
            for op in self.operations:
                try:
                    cleaned_text = op.apply(original_text)
                except Exception as e:
                    self.logger.warning(f"Operation failed: {e}")
                    # Continuing with other operations
                    continue

            doc = Document(
                    page_content=cleaned_text,
                    metadata=document.metadata.copy() if self.preserve_metadata else {}
                    )
            doc.metadata.update({
                'cleaning_timestamp': datetime.now().isoformat(),
                'original_length': original_length,
                'cleaned_length': len(cleaned_text),
                'compression_ratio': 1.0 - (len(cleaned_text)/original_length) if original_length > 0 else 0.0
                })
            return doc
        except Exception as e:
            error_info = {
                    'document_source': document.metadata.get('source_file', 'unknown'),
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                    }
            self._errors.append(error_info)
            raise CleanerError(f"Failed to clean document: {e}", error_info)

    def clean_documents(self, documents: List[Document]) -> List[Document]:
        """
        Clean multiple documents with parallel processing
        """
        
        if not documents:
            self.logger.warning("No documents provided")
            return []

        start_time = datetime.now()
        cleaned_documents = []

        # Parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_doc = {
                    executor.submit(self._clean_single_document, doc): doc for doc in documents
                    }

            for future in as_completed(future_to_doc):
                try:
                    cleaned_doc = future.result()
                    cleaned_documents.append(cleaned_doc)
                except Exception as e:
                    self.logger.error(f"Document cleaning failed: {e}")

        # Update statistics
        end_time = datetime.now()
        
        self.logger.info(f"Cleaning completed in: {(end_time - start_time).total_seconds()}")
        return cleaned_documents
    
    def get_errors(self):
        return self._errors
