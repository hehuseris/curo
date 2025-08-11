from __future__ import annotations

import csv
import json
from typing import Any, Dict


class JSONLWriter:
    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, record: Dict[str, Any]) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


class CSVWriter:
    FIELDNAMES = [
        "url",
        "status",
        "title",
        "meta_description",
        "text_excerpt",
        "num_links",
    ]

    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = open(self.path, "a", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDNAMES)
        if self._fh.tell() == 0:
            self._writer.writeheader()

    def write(self, record: Dict[str, Any]) -> None:
        row = {k: record.get(k) for k in self.FIELDNAMES}
        self._writer.writerow(row)

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass