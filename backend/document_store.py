from __future__ import annotations

from threading import Lock
from typing import Tuple


class DocumentStore:
    """
    Thread-safe in-memory document store.

    OS Concepts Demonstrated:
    - Shared Resource: The document string is shared among threads (clients).
    - Critical Sections: Any mutation or read of mutable shared state is protected.
    - Synchronization: A single mutex (Lock) provides mutual exclusion.
    - Race Condition Avoidance: Only one thread can read/write at a time, ensuring consistency.
    """

    def __init__(self) -> None:
        self._document: str = ""
        self._version: int = 0
        self._lock: Lock = Lock()

    def get_document(self) -> Tuple[str, int]:
        """
        Return the current document and version.

        Guarded read: although Python reads of strings are atomic,
        we guard to ensure the version and content are consistent as a pair.
        """
        with self._lock:
            return self._document, self._version

    def update_document(self, new_content: str) -> int:
        """
        Replace the entire document content and increment version.

        This is a document-level replacement (MVP) with last-write-wins semantics.
        Returns the new version.
        """
        with self._lock:  # Critical section: mutate shared state
            self._document = new_content
            self._version += 1
            return self._version

    def apply_edit(self, operation: dict) -> Tuple[str, int]:
        """
        Apply an edit operation. For MVP we accept full replacement operations:
        {"type": "replace", "content": str}

        Returns (content, version) after applying.

        Future enhancement: Operational Transformation for insert/delete at positions.
        """
        op_type = operation.get("type")
        if op_type == "replace":
            content = operation.get("content", "")
            new_version = self.update_document(content)
            with self._lock:
                return self._document, new_version
        else:
            # Unknown operation; no-op
            with self._lock:
                return self._document, self._version


