from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from datetime import datetime, date
try:
	import numpy as _np
except Exception:  # pragma: no cover
	_np = None


def _make_jsonable(obj: Any) -> Any:
	if is_dataclass(obj):
		return _make_jsonable(asdict(obj))
	if isinstance(obj, dict):
		return {k: _make_jsonable(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_make_jsonable(v) for v in obj]
	if isinstance(obj, (datetime, date)):
		return obj.isoformat()
	if _np is not None and isinstance(obj, getattr(_np, 'generic', ())):
		return obj.item()
	return obj


def save_json(path: str | Path, obj: Any) -> None:
	p = Path(path)
	p.parent.mkdir(parents=True, exist_ok=True)
	obj = _make_jsonable(obj)
	with p.open("w", encoding="utf-8") as f:
		json.dump(obj, f, indent=2, ensure_ascii=False)


def load_json(path: str | Path) -> Any:
	p = Path(path)
	with p.open("r", encoding="utf-8") as f:
		return json.load(f)

