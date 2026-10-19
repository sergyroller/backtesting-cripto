"""Immutable raw dataset storage under data/raw/ with a SHA-256 manifest.

Downloaded payloads are never overwritten: file names embed the content
hash, so identical content maps to the same file (idempotent saves) and
new content always lands in a new file.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backtesting_cripto.domain.exceptions import DataValidationError

MANIFEST_FILENAME = "MANIFEST.json"


@dataclass(frozen=True)
class RawDatasetEntry:
    """One immutable raw file recorded in the manifest."""

    id: str
    source: str
    url: str
    retrieved_at: str
    sha256: str
    first_day: str
    last_day: str
    record_count: int
    license: str
    relative_path: str

    def to_dict(self) -> dict[str, Any]:
        """Manifest representation with plain JSON types."""
        return asdict(self)


def compute_sha256(payload: bytes) -> str:
    """SHA-256 hex digest of a byte payload."""
    return hashlib.sha256(payload).hexdigest()


def compute_file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    return compute_sha256(path.read_bytes())


class RawStore:
    """Immutable storage of downloaded datasets plus their manifest."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    @property
    def manifest_path(self) -> Path:
        return self._root / MANIFEST_FILENAME

    def load_manifest(self) -> list[RawDatasetEntry]:
        """Read the manifest, or an empty list when it does not exist yet."""
        if not self.manifest_path.exists():
            return []
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        datasets = payload.get("datasets", [])
        return [RawDatasetEntry(**entry) for entry in datasets]

    def _write_manifest(self, entries: list[RawDatasetEntry]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        payload = {"datasets": [entry.to_dict() for entry in entries]}
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def save(
        self,
        *,
        dataset_id: str,
        source: str,
        url: str,
        payload: bytes,
        first_day: str,
        last_day: str,
        record_count: int,
        license: str,
        extension: str = ".json",
    ) -> RawDatasetEntry:
        """Persist a raw payload and record it in the manifest.

        The file name embeds the SHA-256 of the content: saving the same
        bytes twice is a no-op, and different content never overwrites an
        existing file.
        """
        digest = compute_sha256(payload)
        relative_path = f"{source}/{dataset_id}_{digest[:16]}{extension}"
        destination = self._root / relative_path

        if destination.exists():
            if compute_file_sha256(destination) != digest:
                msg = f"raw file {relative_path} exists with different content"
                raise DataValidationError(msg)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)

        entry = RawDatasetEntry(
            id=dataset_id,
            source=source,
            url=url,
            retrieved_at=datetime.now(UTC).isoformat(),
            sha256=digest,
            first_day=first_day,
            last_day=last_day,
            record_count=record_count,
            license=license,
            relative_path=relative_path,
        )

        entries = self.load_manifest()
        known_paths = {existing.relative_path for existing in entries}
        if relative_path not in known_paths:
            entries.append(entry)
            self._write_manifest(entries)

        return entry

    def latest_entry(self, dataset_id: str) -> RawDatasetEntry | None:
        """Most recent manifest entry for a dataset id (by last_day, then retrieved_at)."""
        entries = [entry for entry in self.load_manifest() if entry.id == dataset_id]
        if not entries:
            return None
        return max(entries, key=lambda entry: (entry.last_day, entry.retrieved_at))

    def read_payload(self, entry: RawDatasetEntry) -> bytes:
        """Read the immutable raw file of a manifest entry."""
        return (self._root / entry.relative_path).read_bytes()

    def dataset_hash(self) -> str:
        """Deterministic SHA-256 over the manifest content.

        ``retrieved_at`` is excluded: the hash identifies the dataset
        content, not the moment it was downloaded, so re-syncing without
        changes keeps the same hash.
        """
        entries = sorted(
            self.load_manifest(),
            key=lambda entry: (entry.id, entry.retrieved_at, entry.relative_path),
        )
        content = [
            {key: value for key, value in entry.to_dict().items() if key != "retrieved_at"}
            for entry in entries
        ]
        canonical = json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return compute_sha256(canonical.encode("utf-8"))
