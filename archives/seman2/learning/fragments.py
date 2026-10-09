"""DOP fragment parsing, matching, instantiation and linearization.

A fragment is a continuous subtree whose cut points are frontier nodes
(``"(NN )"``). Lexicalized leaves keep their observed word; host trees may
carry sentence indices instead of words. The matcher never encodes
linguistic categories: labels and words are opaque observed data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class FragmentNode:
    label: str
    word: str | None = None
    children: tuple["FragmentNode", ...] = ()
    leaf_index: int | None = None

    @property
    def is_frontier(self) -> bool:
        return self.word is None and not self.children

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def to_bracketed(self, *, resolve: Sequence[str] | None = None) -> str:
        if self.is_frontier:
            return f"({self.label} )"
        if self.is_leaf:
            value = self.word
            if resolve is not None and self.leaf_index is not None:
                value = resolve[self.leaf_index]
            return f"({self.label} {value})"
        inner = " ".join(child.to_bracketed(resolve=resolve) for child in self.children)
        return f"({self.label} {inner})"

    def leaves(self, *, resolve: Sequence[str] | None = None) -> tuple[str, ...]:
        if self.is_frontier:
            return ()
        if self.is_leaf:
            if resolve is not None and self.leaf_index is not None:
                return (resolve[self.leaf_index],)
            return (self.word or "",)
        values: list[str] = []
        for child in self.children:
            values.extend(child.leaves(resolve=resolve))
        return tuple(values)

    def paths(self, prefix: str = "0") -> tuple[str, ...]:
        found = [prefix]
        for index, child in enumerate(self.children):
            found.extend(child.paths(f"{prefix}.{index}"))
        return tuple(found)


def tokenize(source: str) -> list[str]:
    tokens: list[str] = []
    buffer: list[str] = []
    for char in source:
        if char == "(":
            if buffer:
                tokens.append("".join(buffer))
                buffer.clear()
            tokens.append("(")
        elif char == ")":
            if buffer:
                tokens.append("".join(buffer))
                buffer.clear()
            tokens.append(")")
        elif char.isspace():
            if buffer:
                tokens.append("".join(buffer))
                buffer.clear()
        else:
            buffer.append(char)
    if buffer:
        tokens.append("".join(buffer))
    return tokens


def parse_bracketed(
    source: str,
    *,
    sentence: Sequence[str] | None = None,
) -> FragmentNode:
    """Parse a bracketed tree; empty leaves become frontier nodes."""
    tokens = tokenize(source)
    position = 0

    def walk() -> FragmentNode:
        nonlocal position
        if position >= len(tokens) or tokens[position] != "(":
            raise ValueError(f"expected '(' at token {position} of {tokens!r}")
        position += 1
        if position >= len(tokens):
            raise ValueError("unexpected end of fragment")
        label = tokens[position]
        position += 1
        children: list[FragmentNode] = []
        word: str | None = None
        leaf_index: int | None = None
        while position < len(tokens) and tokens[position] != ")":
            token = tokens[position]
            if token == "(":
                children.append(walk())
            else:
                position += 1
                if word is not None:
                    raise ValueError(f"multiple leaves under ({label} ...)")
                word = token
                if sentence is not None:
                    try:
                        leaf_index = int(token)
                    except ValueError:
                        leaf_index = None
        if position >= len(tokens):
            raise ValueError("unbalanced fragment")
        position += 1
        if word == "":
            word = None
        return FragmentNode(label=label, word=word, children=tuple(children), leaf_index=leaf_index)

    node = walk()
    if position != len(tokens):
        raise ValueError("trailing tokens after fragment")
    return node


@dataclass(frozen=True, slots=True)
class FragmentMatch:
    """One occurrence of a fragment inside a host tree."""

    root_path: str
    bindings: Mapping[str, str]
    covered_leaves: tuple[str, ...]
    bracketed: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "root_path": self.root_path,
            "bindings": dict(self.bindings),
            "covered_leaves": list(self.covered_leaves),
            "bracketed": self.bracketed,
        }


def _node_at(root: FragmentNode, path: str) -> FragmentNode:
    node = root
    if path in {"", "0"}:
        return node
    for part in path.split(".")[1:]:
        node = node.children[int(part)]
    return node


def _match_here(
    fragment: FragmentNode,
    host: FragmentNode,
    *,
    resolve: Sequence[str] | None,
    prefix: str,
    bindings: dict[str, str],
) -> bool:
    if fragment.label != host.label:
        return False
    if fragment.is_frontier:
        bindings[prefix] = host.to_bracketed(resolve=resolve)
        return True
    if fragment.is_leaf:
        if not host.is_leaf:
            return False
        fragment_word = fragment.word or ""
        if fragment.leaf_index is not None and resolve is not None:
            fragment_word = resolve[fragment.leaf_index]
        host_word = host.word or ""
        if host.leaf_index is not None and resolve is not None:
            host_word = resolve[host.leaf_index]
        return fragment_word == host_word
    if len(fragment.children) != len(host.children):
        return False
    for index, (fragment_child, host_child) in enumerate(
        zip(fragment.children, host.children)
    ):
        if not _match_here(
            fragment_child,
            host_child,
            resolve=resolve,
            prefix=f"{prefix}.{index}",
            bindings=bindings,
        ):
            return False
    return True


def match_fragment(
    fragment: FragmentNode,
    host: FragmentNode,
    *,
    sentence: Sequence[str] | None = None,
) -> tuple[FragmentMatch, ...]:
    """Return every occurrence of ``fragment`` inside ``host``."""
    matches: list[FragmentMatch] = []
    stack: list[tuple[str, FragmentNode]] = [("0", host)]
    while stack:
        path, node = stack.pop()
        for index, child in enumerate(node.children):
            stack.append((f"{path}.{index}", child))
        bindings: dict[str, str] = {}
        if _match_here(fragment, node, resolve=sentence, prefix=path, bindings=bindings):
            matches.append(
                FragmentMatch(
                    root_path=path,
                    bindings=dict(sorted(bindings.items())),
                    covered_leaves=node.leaves(resolve=sentence)
                    if not fragment.is_frontier
                    else (),
                    bracketed=node.to_bracketed(resolve=sentence),
                )
            )
    matches.sort(key=lambda row: (row.root_path, tuple(row.bindings.items())))
    return tuple(matches)


def instantiate(
    fragment: FragmentNode,
    bindings: Mapping[str, FragmentNode | str],
    *,
    root_path: str = "0",
) -> FragmentNode:
    """Fill frontier sites of ``fragment`` with provided subtrees or words."""

    def resolve_slot(path: str, node: FragmentNode) -> FragmentNode:
        if node.is_frontier and path in bindings:
            replacement = bindings[path]
            if isinstance(replacement, str):
                if replacement.startswith("("):
                    return parse_bracketed(replacement)
                return FragmentNode(label=node.label, word=replacement)
            return replacement
        children = tuple(
            resolve_slot(f"{path}.{index}", child)
            for index, child in enumerate(node.children)
        )
        return FragmentNode(label=node.label, word=node.word, children=children, leaf_index=node.leaf_index)

    return resolve_slot(root_path, fragment)


def linearize(node: FragmentNode, *, sentence: Sequence[str] | None = None) -> str:
    """Join observed leaves; never invent missing lexical material."""
    words = [word for word in node.leaves(resolve=sentence) if word]
    result = ""
    no_leading_space = set(".,;:!?)]}")
    for word in words:
        if not result or word[:1] in no_leading_space:
            result += word
        else:
            result += " " + word
    return result


def fragment_signature(fragment: FragmentNode) -> str:
    """Canonical form used for identity: holes and lexical items preserved."""
    return fragment.to_bracketed()
