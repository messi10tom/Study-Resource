import mimetypes
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Union
from langchain_community.document_loaders import (
        PyMuPDFLoader,
        TextLoader,
        UnstructuredWordDocumentLoader,
        UnstructuredPowerPointLoader
        )
from langchain_core.documents.base import Document

class DataLoaderError(Exception):
    def __init__(self, message):
        super().__init__(message)

class DataLoader:
    """
    Data loader implementation, supports documents like pdf, pptx, etc(will be added)
    """

    SUPPORTED_EXTENSIONS = {
            '.pdf': PyMuPDFLoader,
            '.docx': UnstructuredWordDocumentLoader,
            '.pptx': UnstructuredPowerPointLoader
            }

    def __init__(self,
                 file_path: Optional[Union[str, Path]] = None,
                 dir_path: Optional[Union[str, Path]] = None,
                 filetype: Optional[str] = ".pdf",
                 recursive: bool = False,
                 max_workers: int = 4
                 ):
        """
        DataLoader configuration

        Args:
            file_path: Path to a single file
            dir_path: Path to directory containing files
            filetype: File extension filter for directory loading
        """
        self.file_path = Path(file_path) if file_path else None
        self.dir_path = Path(dir_path) if dir_path else None

        self.recursive = recursive
        self.filetype = filetype.lower() if filetype else "./pdf"
        self.max_workers = max_workers

        self._errors = []
        self._loaded_documents = []
        self._metadata: Dict[str, Any] = {}
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate the current configuration"""
        if not self.file_path and not self.dir_path:
            raise DataLoaderError("Either 'file_path' or 'dir_path' must be provided")

        if self.file_path and self.dir_path:
            raise DataLoaderError("Provide either 'file_path' or 'dir_path' not both")

        if self.filetype not in self.SUPPORTED_EXTENSIONS:
            raise DataLoaderError(f"Unsupported filetpe: {self.filetype}")

    def _get_loader_class(self, file_path: Path) -> type:
        """Get the appropriate loader class"""
        extension = file_path.suffix.lower()

        if extension in self.SUPPORTED_EXTENSIONS:
            return self.SUPPORTED_EXTENSIONS[extension]

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith('text/'):
                return TextLoader
            elif mime_type == 'application/pdf':
                return PyMuPDFLoader


        # Unknow filetype
        return TextLoader

    def _load_single_file(self, file_path:Path) -> List[Document]:
        """
        Loads a single file
        
        Returns:
            List of loaded documents
        """
        documents = []

        try:
            # TODO: File validation code

            loader_class = self._get_loader_class(file_path)
            loader = loader_class(str(file_path))

            loaded_docs = loader.load()

            # Adds metadata
            for doc in loaded_docs:
                doc.metadata.update({
                    'source_file': str(file_path),
                    'file_size': file_path.stat().st_size,
                    'load_timestamp': datetime.now().isoformat(),
                    'file_extension': file_path.suffix.lower()
                })

            documents.extend(loaded_docs)

        except Exception as e:
            error_info = {
                    'file_path': str(file_path),
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                    }
            self._errors.append(error_info)

        return documents

    def _get_files_from_directory(self) -> List[Path]:
        """
        Get list of path to files based on the configuration
        """
        files = []

        try:
            # TODO: Optimize it and validate
            if self.recursive:
                pattern = f"**/*{self.filetype}"
                files = list(self.dir_path.glob(pattern))
            else:
                pattern = f"*/{self.filetype}"
                files = list(self.dir_path.glob(pattern))
        except Exception as e:
            raise DataLoaderError(f"Error scanning directory {self.dir_path}: {e}")

        return files

    def load_from_file(self) -> List[Document]:
        """
        Loads from single file
        """
        if not self.file_path:
            raise DataLoaderError("file_path is not set")

        documents = self._load_single_file(self.file_path)
        self._loaded_documents.extend(documents)

        return documents

    def load_from_dir(self) -> List[Document]:
        """
        Loads documents from directory
        """

        if not self.dir_path:
            raise DataLoaderError("dir_path is not set")

        if not self.dir_path.exists():
            raise DataLoaderError("Directory does not exists")

        if not self.dir_path.is_dir():
            raise DataLoaderError(f"'{self.dir_path}' is not a directory")

        files = self._get_files_from_directory()

        if not files:
            return []

        all_documents = []

        # Parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {
                    executor.submit(self._load_single_file, file_path): file_path for file_path in files
                    }

            for future in as_completed(future_to_file):
                try:
                    documents = future.result()
                    all_documents.extend(documents)
                except Exception as e:
                    pass # Log

        self._loaded_documents.extend(all_documents)
        return all_documents

    def load(self) -> List[Document]:
        """
        Loads documents based on configuration
        """

        start_time = datetime.now()
        
        if self.file_path:
            documents = self.load_from_file()
        else:
            documents = self.load_from_dir()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Update metadata
        self._metadata = {
                'total_documents': len(documents),
                'total_errors': len(self._errors),
                'load_duration_seconds': duration,
                'load_timestamp': start_time.isoformat(),
                'source_type': 'file' if self.file_path else 'directory',
                'source_path': str(self.file_path or self.dir_path)
                }
        return documents

# TODO: Make some @property functions
