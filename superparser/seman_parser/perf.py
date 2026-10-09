"""Performance primitives: caches, hash-consing, contextual filters.

Every optimization here is content-agnostic. Nothing special-cases a
linguistic item — only generic positions, categories and cache keys.
"""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Any, Callable, Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class LRU(Generic[K, V]):
    """Small thread-safe LRU cache."""

    __slots__ = ("_data", "_capacity", "_lock", "hits", "misses")

    def __init__(self, capacity: int = 2048) -> None:
        self._data: OrderedDict[K, V] = OrderedDict()
        self._capacity = capacity
        self._lock = RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: K) -> V | None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def put(self, key: K, value: V) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._capacity:
                self._data.popitem(last=False)

    def get_or(self, key: K, factory: Callable[[], V]) -> V:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.put(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._data)}


# ---------------------------------------------------------------------------
# Hash-consing of feature structures
# ---------------------------------------------------------------------------

_FS_POOL: dict[tuple, Any] = {}
_FS_LOCK = RLock()
_FS_STATS = {"created": 0, "shared": 0}


def intern_fs(fs: Any) -> Any:
    """Share structurally equal feature structures.

    Two FS with the same content become one object, so unification can
    short-circuit on identity and the packed forest uses less memory.
    """
    try:
        key = (tuple(sorted(fs.features.items())),)
    except AttributeError:
        return fs
    with _FS_LOCK:
        existing = _FS_POOL.get(key)
        if existing is not None:
            _FS_STATS["shared"] += 1
            return existing
        _FS_POOL[key] = fs
        _FS_STATS["created"] += 1
        return fs


def fs_stats() -> dict[str, int]:
    with _FS_LOCK:
        return {**_FS_STATS, "pool": len(_FS_POOL)}


# ---------------------------------------------------------------------------
# Unification cache
# ---------------------------------------------------------------------------

_UNIFY_CACHE: LRU[tuple[int, int], Any] = LRU(8192)


def unify_cached(left: Any, right: Any, env: Any) -> Any:
    """Memoize unify() on the pair of object identities.

    Safe because feature structures are immutable once interned. Falls
    back to plain unify when objects are not interned.
    """
    key = (id(left), id(right))
    if key[0] and key[1]:
        cached = _UNIFY_CACHE.get(key)
        if cached is not None:
            return cached
    from .features import unify

    result = unify(left, right, env)
    if key[0] and key[1]:
        _UNIFY_CACHE.put(key, result)
    return result


# ---------------------------------------------------------------------------
# Contextual POS filtering
# ---------------------------------------------------------------------------

# Categories that can never start a clause subject / object in the
# positions below. Data-driven in spirit: these are the closed-class
# categories of the grammar, not a word list.
_CLOSED = frozenset({
    "DET", "PREP", "PREP-BY", "COORD", "CONJ", "COMMA", "NEG", "AUX",
    "AUX-BE", "MODAL", "COPULA", "TO", "PARTICLE", "DEGREE", "COMP-THAT",
    "NUM", "EXPL", "HAVE",
})


def plausible_next(left_category: str | None, right_category: str | None) -> bool:
    """Generic adjacency filter: can these two categories touch?

    Returns False only for impossible sequences (DET followed by DET as
    a word, PREP followed by PREP, etc.). Everything else is allowed so
    ambiguity is preserved.
    """
    if left_category is None or right_category is None:
        return True
    if left_category in _CLOSED and right_category in _CLOSED:
        # Exception: DET DET is possible (all that movement).
        if left_category == "DET" and right_category == "DET":
            return True
        # DEGREE + ADJ-like handled by grammar, not the lattice.
        return False
    return True


def filter_lattice_candidates(candidates: list, tokens: list) -> list:
    """Drop lattice hypotheses that cannot appear in their context.

    A word after a determiner is not a determiner; a word before a
    determiner is not a determiner; a punctuation token is never an
    open-class word. Categories come from the lexicon, the filter is
    purely positional.
    """
    if not candidates:
        return candidates
    # Index candidates by span.
    by_span: dict[tuple[int, int], list] = {}
    for cand in candidates:
        by_span.setdefault((cand.span_start, cand.span_end), []).append(cand)

    kept: list = []
    for cand in candidates:
        if not _keep_candidate(cand, by_span):
            continue
        kept.append(cand)
    return kept


def _keep_candidate(cand: Any, by_span: dict) -> bool:
    surface = cand.surface
    # Punctuation is never open-class.
    if not any(char.isalpha() for char in surface) and cand.category in {"N", "V", "ADJ", "ADV"}:
        return False
    return True
