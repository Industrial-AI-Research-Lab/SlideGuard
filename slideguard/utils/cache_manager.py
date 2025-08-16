import os
import pickle
from pathlib import Path
from abc import ABC
from typing import Any, AsyncIterable, Callable, Generic, Iterable, List, Optional, Tuple, TypeVar, Union
from pydantic import BaseModel

from slideguard.schemes import Slideable


T = TypeVar('T', bound=Slideable)
U = TypeVar('U')

class CacheManager(Generic[T, U], ABC):
    """Async cache manager for storing processing results"""
    def __init__(self, cache_dir: Union[Path, str] = ".slideguard_cache/evaluations"):
        self.cache_dir = cache_dir if isinstance(cache_dir, Path) else Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_hash_id(self, key: BaseModel | str ) -> str:
        return hash(key)

    async def _get_path(self, hash_id: str, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> Path:
        # Handle case where slide_id is None (deck-level criteria)
        if slide_id is None:
            return os.path.join(self.cache_dir, os.path.basename(deck_name), criteria_id, f"{hash_id}.pickle")
        else:
            return os.path.join(self.cache_dir, os.path.basename(deck_name), criteria_id, str(slide_id), f"{hash_id}.pickle")

    async def _get(self, hash_id: str, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> Optional[Any]:
        """Retrieve cached item if exists"""
        cache_path = await self._get_path(hash_id, deck_name, criteria_id, slide_id)
        
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        
        return data

    async def _put(self, hash_id: str, value: Any, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> None:
        """Store item in cache"""
        cache_path = await self._get_path(hash_id, deck_name, criteria_id, slide_id)
        base_dir = os.path.dirname(cache_path)
        os.makedirs(base_dir, exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(value, f)

    async def get(self, key: BaseModel | str, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> Optional[Any]:
        hash_id = self._get_hash_id(key)
        return await self._get(hash_id, deck_name, criteria_id, slide_id)

    async def put(self, key: BaseModel | str, value: Any, deck_name: str, criteria_id: str, slide_id: Optional[str] = None) -> None:
        hash_id = self._get_hash_id(key)
        await self._put(hash_id, value, deck_name, criteria_id, slide_id)

    async def compute_with_cache(self,
                                 deck_name: str,
                                 criteria_id: str,
                                 inputs: List[T],
                                 func: Callable[[Iterable[Tuple[int, T]]], AsyncIterable[Tuple[int, U]]]) -> List[U]:
        results = []
        
        to_compute = []

        for i, in_ in enumerate(inputs):
            hash_id = self._get_hash_id(in_)
            cached_result = await self._get(hash_id, deck_name, criteria_id, in_.slide_id)
            
            if cached_result is not None:
                results.append((i, cached_result))
            else:
                to_compute.append((i, in_))

        print(f"Found cached results: {len(results)} / {len(inputs)}")

        if to_compute:
            async for i, result in func(to_compute):
                hash_id = self._get_hash_id(inputs[i])
                await self._put(hash_id, result, deck_name, criteria_id, inputs[i].slide_id)
                results.append((i, result))

        results = [result for _, result in sorted(results, key=lambda x: x[0])]
        
        return results

