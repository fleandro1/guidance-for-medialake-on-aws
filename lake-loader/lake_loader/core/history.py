"""Ingest history management for LakeLoader application."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from lake_loader.core.config import get_data_dir
from lake_loader.core.models import HistoryRecord


class IngestHistory:
    """Manages the history of completed ingest tasks."""

    def __init__(self, history_path: Optional[Path] = None, max_records: int = 10000):
        """
        Initialize the history manager.

        Args:
            history_path: Path to history JSON file. Defaults to data directory.
            max_records: Maximum number of records to keep.
        """
        if history_path is None:
            history_path = get_data_dir() / "history.json"

        self._history_path = history_path
        self._max_records = max_records
        self._records: List[HistoryRecord] = []
        self._loaded = False

    @property
    def records(self) -> List[HistoryRecord]:
        """Get all history records (most recent first)."""
        if not self._loaded:
            self.load()
        return self._records

    def load(self) -> None:
        """Load history from file."""
        self._records = []

        if self._history_path.exists():
            try:
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for item in data:
                    try:
                        record = HistoryRecord.from_dict(item)
                        self._records.append(record)
                    except (KeyError, ValueError) as e:
                        print(f"Warning: Skipping invalid history record: {e}")

            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load history from {self._history_path}: {e}")

        self._loaded = True

    def save(self) -> None:
        """Save history to file."""
        # Ensure directory exists
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

        # Trim to max records before saving
        if len(self._records) > self._max_records:
            self._records = self._records[: self._max_records]

        data = [record.to_dict() for record in self._records]

        try:
            with open(self._history_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error: Failed to save history to {self._history_path}: {e}")
            raise

    def append(self, record: HistoryRecord) -> None:
        """
        Add a record to the history.

        Records are prepended (most recent first).
        """
        if not self._loaded:
            self.load()

        self._records.insert(0, record)

        # Trim if exceeding max records
        if len(self._records) > self._max_records:
            self._records = self._records[: self._max_records]

        self.save()

    def delete_latest(self, n: int) -> int:
        """
        Delete the latest n records.

        Args:
            n: Number of records to delete from the beginning.

        Returns:
            Number of records actually deleted.
        """
        if not self._loaded:
            self.load()

        count = min(n, len(self._records))
        self._records = self._records[count:]
        self.save()
        return count

    def delete_oldest(self, n: int) -> int:
        """
        Delete the oldest n records.

        Args:
            n: Number of records to delete from the end.

        Returns:
            Number of records actually deleted.
        """
        if not self._loaded:
            self.load()

        count = min(n, len(self._records))
        if count > 0:
            self._records = self._records[:-count]
        self.save()
        return count

    def clear_all(self) -> int:
        """
        Clear all history records.

        Returns:
            Number of records deleted.
        """
        if not self._loaded:
            self.load()

        count = len(self._records)
        self._records = []
        self.save()
        return count

    def get_filtered(
        self,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> List[HistoryRecord]:
        """
        Get filtered history records.

        Args:
            status_filter: Filter by status (None = all).
            search_text: Filter by filename contains (case-insensitive).

        Returns:
            Filtered list of records.
        """
        if not self._loaded:
            self.load()

        records = self._records

        if status_filter:
            records = [r for r in records if r.status.lower() == status_filter.lower()]

        if search_text:
            search_lower = search_text.lower()
            records = [r for r in records if search_lower in r.filename.lower()]

        return records

    def export_csv(self, output_path: Path) -> int:
        """
        Export history to CSV file.

        Args:
            output_path: Path to output CSV file.

        Returns:
            Number of records exported.
        """
        if not self._loaded:
            self.load()

        fieldnames = [
            "timestamp",
            "filename",
            "file_path",
            "file_size",
            "connector_id",
            "connector_name",
            "destination_path",
            "status",
            "duration_seconds",
            "error_message",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for record in self._records:
                row = record.to_dict()
                writer.writerow(row)

        return len(self._records)

    def count(self) -> int:
        """Get total number of records."""
        if not self._loaded:
            self.load()
        return len(self._records)

    def count_by_status(self) -> Dict[str, int]:
        """Get count of records by status."""
        if not self._loaded:
            self.load()

        counts: Dict[str, int] = {}
        for record in self._records:
            status = record.status
            counts[status] = counts.get(status, 0) + 1

        return counts
