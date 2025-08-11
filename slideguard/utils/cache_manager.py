import os
import pickle
from pathlib import Path
from typing import Any, Optional, Union

class CacheManager:
    """Async cache manager for storing processing results"""
    def __init__(self, cache_dir: Union[Path, str]):
        self.cache_dir = cache_dir if isinstance(cache_dir, Path) else Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def _get_path(self, hash_id: str, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> Path:
        # Handle case where slide_id is None (deck-level criteria)
        if slide_id is None:
            return os.path.join(self.cache_dir, os.path.basename(deck_name), criteria_id, f"{hash_id}.pickle")
        else:
            return os.path.join(self.cache_dir, os.path.basename(deck_name), criteria_id, slide_id, f"{hash_id}.pickle")

    async def get(self, hash_id: str, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> Optional[Any]:
        """Retrieve cached item if exists"""
        cache_path = await self._get_path(hash_id, deck_name, criteria_id, slide_id)
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        return data

    async def put(self, hash_id: str, value: Any, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> None:
        """Store item in cache"""
        cache_path = await self._get_path(hash_id, deck_name, criteria_id, slide_id)
        base_dir = os.path.dirname(cache_path)
        os.makedirs(base_dir, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(value, f)