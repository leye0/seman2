"""disco-dop bridge for recurring structural fragments."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


class DiscoDopAdapter:
    def __init__(self, *, strict: bool = False) -> None:
        self._error: str | None = None
        self._tree_class: Any | None = None
        self._recurring: Any | None = None
        self._binarize: Any | None = None
        self._unbinarize: Any | None = None
        try:
            from discodop.fragments import recurringfragments  # type: ignore
            from discodop.tree import Tree  # type: ignore
            from discodop.treetransforms import binarize, unbinarize  # type: ignore

            self._tree_class = Tree
            self._recurring = recurringfragments
            self._binarize = binarize
            self._unbinarize = unbinarize
        except (ImportError, OSError) as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            if strict:
                raise RuntimeError(f"local disco-dop unavailable: {exc}") from exc

    @property
    def available(self) -> bool:
        return (
            self._tree_class is not None
            and self._recurring is not None
            and self._binarize is not None
        )

    @property
    def status(self) -> dict[str, Any]:
        return {"available": self.available, "error": self._error}

    def probe(self) -> dict[str, Any]:
        """Functional check: two trees must yield at least one recurring fragment."""
        if not self.available:
            return {"ok": False, "error": self._error or "local disco-dop unavailable"}
        try:
            rows = self.recurring(
                [
                    "(S (NP (DT 0) (NN 1)) (VP (VBD 2)))",
                    "(S (NP (DT 0) (NN 1)) (VP (VBD 2)))",
                ],
                [("the", "dog", "ran"), ("the", "cat", "ran")],
                max_depth=3,
            )
        except Exception as exc:  # noqa: BLE001 - probe must report, not raise
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return {"ok": bool(rows), "fragments": len(rows), "error": None}

    def recurring(
        self,
        trees: Sequence[str],
        sentences: Sequence[Sequence[str]],
        *,
        max_depth: int = 5,
    ) -> tuple[dict[str, Any], ...]:
        if not self.available:
            raise RuntimeError(self._error or "local disco-dop unavailable")
        assert self._tree_class is not None and self._recurring is not None
        assert self._binarize is not None and self._unbinarize is not None
        if len(trees) != len(sentences):
            raise ValueError("tree and sentence counts differ")
        parsed = [
            self._binarize(self._tree_class.parse(tree, parse_leaf=int))
            for tree in trees
        ]
        result = self._recurring(
            parsed,
            [list(sentence) for sentence in sentences],
            numproc=1,
            disc=False,
            indices=True,
            maxdepth=max_depth,
        )
        rows: list[dict[str, Any]] = []
        for fragment, indices in result.items():
            try:
                support = tuple(sorted(int(value) for value in indices))
            except TypeError:
                support = ()
            if isinstance(fragment, tuple):
                fragment = fragment[0]
            normalized = self._normalize_fragment(str(fragment))
            rows.append({"fragment": normalized, "tree_indices": support, "support": len(support)})
        return tuple(sorted(rows, key=lambda row: (-row["support"], str(row["fragment"]))))

    def _normalize_fragment(self, source: str) -> str:
        """Undo binarization artifacts so labels match the native analysis."""
        assert self._tree_class is not None and self._unbinarize is not None
        try:
            tree = self._tree_class.parse(source, parse_leaf=str)
        except ValueError:
            return source
        restored = self._unbinarize(tree)
        return str(restored)
