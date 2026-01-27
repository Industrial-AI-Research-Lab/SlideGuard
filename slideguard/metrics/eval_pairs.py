from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from filelock import FileLock

from slideguard.metrics.schemas import EvalPair, EvalPairsConfig


class EvalPairsManager:
    def __init__(self, pairs_path: Path = Path("resources/eval_pairs.json")) -> None:
        self.pairs_path = pairs_path
        self.pairs_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = pairs_path.with_suffix(pairs_path.suffix + ".lock")

    def load_pairs(
        self,
        filter_tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        exclude_disabled: bool = False,
    ) -> List[EvalPair]:
        config = self._read_config()
        pairs = config.pairs
        if exclude_disabled:
            pairs = [p for p in pairs if p.enabled]
        if filter_tags:
            tags = set(filter_tags)
            pairs = [p for p in pairs if tags.intersection(p.tags)]
        if exclude_tags:
            excluded = set(exclude_tags)
            pairs = [p for p in pairs if not excluded.intersection(p.tags)]
        return pairs

    def add_pair(self, pair: EvalPair) -> None:
        config = self._read_config()
        config.pairs.append(pair)
        self._write_config(config)

    def update_pair(self, index: int, pair: EvalPair) -> None:
        config = self._read_config()
        if index < 0 or index >= len(config.pairs):
            raise IndexError("Eval pair index out of range")
        config.pairs[index] = pair
        self._write_config(config)

    def remove_pair(self, index: int) -> None:
        config = self._read_config()
        if index < 0 or index >= len(config.pairs):
            raise IndexError("Eval pair index out of range")
        del config.pairs[index]
        self._write_config(config)

    def save_pairs(self, pairs: List[EvalPair], no_update: bool = False) -> None:
        config = EvalPairsConfig(
            pairs=pairs,
            last_updated=None if no_update else datetime.utcnow(),
        )
        self._write_config(config)

    def get_all_tags(self) -> List[str]:
        config = self._read_config()
        tags = set()
        for pair in config.pairs:
            tags.update(pair.tags)
        return sorted(tags)

    def get_pairs_by_tag(self, tag: str) -> List[EvalPair]:
        return [pair for pair in self._read_config().pairs if tag in pair.tags]

    def _read_config(self) -> EvalPairsConfig:
        lock = FileLock(str(self.lock_path))
        with lock:
            if not self.pairs_path.exists():
                return EvalPairsConfig()
            data = json.loads(self.pairs_path.read_text(encoding="utf-8"))
            return EvalPairsConfig.model_validate(data)

    def _write_config(self, config: EvalPairsConfig) -> None:
        lock = FileLock(str(self.lock_path))
        payload = config.model_dump(mode="json")
        tmp_path = self.pairs_path.with_suffix(".tmp")
        with lock:
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp_path, self.pairs_path)







