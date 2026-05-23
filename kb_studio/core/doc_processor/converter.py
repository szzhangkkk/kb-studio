"""Document to Markdown conversion using markitdown."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass

from markitdown import MarkItDown


@dataclass
class ConvertedDocument:
    source_path: str
    markdown: str
    file_type: str
    metadata: dict


SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".html", ".htm", ".csv", ".json", ".xml", ".txt", ".md",
    ".epub", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".wav", ".mp3", ".mp4",
}


class DocumentConverter:
    """Wraps markitdown to convert various document formats to Markdown."""

    def __init__(self, llm_client=None, llm_model: str | None = None):
        kwargs = {}
        if llm_client:
            kwargs["llm_client"] = llm_client
        if llm_model:
            kwargs["llm_model"] = llm_model
        self._md = MarkItDown(**kwargs)

    def convert_file(self, file_path: str) -> ConvertedDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        result = self._md.convert(str(path))
        return ConvertedDocument(
            source_path=str(path),
            markdown=result.text_content,
            file_type=path.suffix.lower(),
            metadata={
                "filename": path.name,
                "size_bytes": path.stat().st_size,
                "title": getattr(result, "title", path.stem),
            },
        )

    def convert_directory(self, dir_path: str) -> list[ConvertedDocument]:
        """Convert all supported files in a directory recursively."""
        documents = []
        dirp = Path(dir_path)
        if not dirp.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        for file_path in sorted(dirp.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    doc = self.convert_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    print(f"Warning: failed to convert {file_path}: {e}")
        return documents
