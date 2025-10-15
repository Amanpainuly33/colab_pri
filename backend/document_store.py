from __future__ import annotations

from threading import Lock
from typing import Tuple, Optional
import time


class DocumentStore:
    """
    Thread-safe in-memory document store.

    OS Concepts Demonstrated:
    - Shared Resource: The document string is shared among threads (clients).
    - Critical Sections: Any mutation or read of mutable shared state is protected.
    - Synchronization: A single mutex (Lock) provides mutual exclusion.
    - Race Condition Avoidance: Only one thread can read/write at a time, ensuring consistency.
    """

    def __init__(self, lock_timeout: float = 3.0) -> None:
        self._document: str = ""
        self._version: int = 0
        self._lock: Lock = Lock()
        # Editor lock state
        self._editor_lock_holder: Optional[str] = None
        self._editor_lock_expires: float = 0.0
        self._lock_timeout: float = lock_timeout

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

    # --- Locking API ---

    def try_acquire_editor_lock(self, client_id: str) -> bool:
        """
        Attempt to acquire the editor lock for a client.
        Returns True if acquired (or already held by client), False otherwise.
        """
        with self._lock:
            now = time.time()
            # Expire old lock if needed
            if self._editor_lock_holder and now > self._editor_lock_expires:
                self._editor_lock_holder = None

            if not self._editor_lock_holder or self._editor_lock_holder == client_id:
                self._editor_lock_holder = client_id
                self._editor_lock_expires = now + self._lock_timeout
                return True
            return False

    def release_editor_lock(self, client_id: str) -> None:
        """Release the editor lock if held by this client."""
        with self._lock:
            if self._editor_lock_holder == client_id:
                self._editor_lock_holder = None
                self._editor_lock_expires = 0.0

    def renew_editor_lock(self, client_id: str) -> bool:
        """Renew the editor lock if held by this client; returns True on success."""
        with self._lock:
            now = time.time()
            if self._editor_lock_holder == client_id and now <= self._editor_lock_expires:
                self._editor_lock_expires = now + self._lock_timeout
                return True
            return False

    def get_lock_status(self) -> Tuple[Optional[str], bool]:
        """Return (lock_holder_id, is_locked), expiring stale locks."""
        with self._lock:
            now = time.time()
            if self._editor_lock_holder and now > self._editor_lock_expires:
                self._editor_lock_holder = None
            return self._editor_lock_holder, self._editor_lock_holder is not None

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


