from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def save_json(path: str | Path, obj: Any) -> None:
	p = Path(path)
	p.parent.mkdir(parents=True, exist_ok=True)
	if is_dataclass(obj):
		obj = asdict(obj)
	with p.open("w", encoding="utf-8") as f:
		json.dump(obj, f, indent=2, ensure_ascii=False)


def load_json(path: str | Path) -> Any:
	p = Path(path)
	with p.open("r", encoding="utf-8") as f:
		return json.load(f)

