"""disco-dop bridge for recurring structural fragments."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


class DiscoDopAdapter:
    def __init__(self, *, strict: bool = False) -> None:
        self._error: str | None = None
        self._tree_class: Any | None = None
        self._recurring: Any | None = None
        try:
            from discodop.fragments import recurringfragments  # type: ignore
            from discodop.tree import Tree  # type: ignore

            self._tree_class = Tree
            self._recurring = recurringfragments
        except (ImportError, OSError) as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            if strict:
                raise RuntimeError(f"local disco-dop unavailable: {exc}") from exc

    @property
    def available(self) -> bool:
        return self._tree_class is not None and self._recurring is not None

    @property
    def status(self) -> dict[str, Any]:
        return {"available": self.available, "error": self._error}

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
        if len(trees) != len(sentences):
            raise ValueError("tree and sentence counts differ")
        parsed = [self._tree_class.parse(tree, parse_leaf=int) for tree in trees]
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
            rows.append({"fragment": fragment, "tree_indices": support, "support": len(support)})
        return tuple(sorted(rows, key=lambda row: (-row["support"], str(row["fragment"]))))
