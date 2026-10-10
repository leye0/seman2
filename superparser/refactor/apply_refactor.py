#!/usr/bin/env python3
"""Apply the optional Seman2 fastpath overlay to an existing superparser checkout.

No GitHub writes. Backs up changed files and refuses unexpected source variants.
Usage: python apply_refactor.py /path/to/seman2/superparser [--dry-run] [--merge-wordnet]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
MARKER = "# SEMAN2_FASTPATH_LAZY_PROVENANCE_V1"

LAZY_CLASS = '''# SEMAN2_FASTPATH_LAZY_PROVENANCE_V1
class _DeferredProvenanceChildren:
    """Hold child items; expand recursive provenance only on external export.

    Unlike eagerly generated dictionaries, this retains references to the
    children already kept by the packed forest. It supports iteration and
    indexing, with the same dictionary shape as the previous children list.
    """

    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        for child in self.items:
            yield child.provenance.as_dict()

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [child.provenance.as_dict() for child in self.items[index]]
        return self.items[index].provenance.as_dict()


'''


def patch_chart(source: str) -> tuple[str, bool]:
    if MARKER in source:
        return source, False
    if source.count('@dataclass(frozen=True, slots=True)\nclass Provenance:') != 1:
        raise ValueError("unexpected chart.py: Provenance declaration not found")
    if source.count('return {"source": self.source, "detail": dict(self.detail)}') != 1:
        raise ValueError("unexpected chart.py: provenance serializer differs")
    eager = '"children": [child.provenance.as_dict() for child in children],'
    if source.count(eager) != 1:
        raise ValueError("unexpected chart.py: eager provenance expression differs")
    source = source.replace(
        '@dataclass(frozen=True, slots=True)\nclass Provenance:',
        LAZY_CLASS + '@dataclass(frozen=True, slots=True)\nclass Provenance:', 1,
    )
    source = source.replace(
        'return {"source": self.source, "detail": dict(self.detail)}',
        'detail = dict(self.detail)\n'
        '        if isinstance(detail.get("children"), _DeferredProvenanceChildren):\n'
        '            detail["children"] = list(detail["children"])\n'
        '        return {"source": self.source, "detail": detail}', 1,
    )
    source = source.replace(eager, '"children": _DeferredProvenanceChildren(children),', 1)
    return source, True


def patch_wordnet_static_merge(source: str) -> tuple[str, bool]:
    """Opt-in correctness fix: static words do not shadow additional WN POS.

    Deliberately opt-in: restoring previously hidden POS can increase chart
    branching. Run coverage/performance comparisons before enabling in prod.
    """
    marker = '        # SEMAN2_FASTPATH_STATIC_WORDNET_MERGE_V1\n'
    if marker in source:
        return source, False
    needle = (
        '        found = list(self._by_surface.get(key, ()))\n'
        '        if found:\n'
        '            return found\n'
        '        # The surface may itself be a lemma'
    )
    if source.count(needle) != 1:
        raise ValueError("unexpected lexicon.py: static POS shadow path differs")
    source = source.replace(needle,
        '        found = list(self._by_surface.get(key, ()))\n'
        + marker
        + '        # Merge static and WordNet categories without losing either.\n'
        + '        # The surface may itself be a lemma', 1)
    return source, True


def find_root(arg: str) -> Path:
    root = Path(arg).expanduser().resolve()
    if (root / 'superparser' / 'seman_parser' / 'chart.py').is_file():
        return root / 'superparser'
    if (root / 'seman_parser' / 'chart.py').is_file():
        return root
    raise FileNotFoundError(f"cannot find superparser/seman_parser/chart.py under {root}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', help='path to seman2 root or superparser directory')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--merge-wordnet', action='store_true', help='opt-in static + WordNet POS merge')
    args = ap.parse_args()
    root = find_root(args.project)
    destination = root / 'seman_parser' / 'fastpath.py'
    source_new = HERE / 'overlay' / 'seman_parser' / 'fastpath.py'
    test_new = HERE / 'overlay' / 'tests' / 'test_fastpath.py'
    paths = {
        root / 'seman_parser' / 'chart.py': patch_chart,
    }
    if args.merge_wordnet:
        paths[root / 'seman_parser' / 'lexicon.py'] = patch_wordnet_static_merge
    staged: dict[Path, bytes] = {}
    for file, patch in paths.items():
        updated, changed = patch(file.read_text(encoding='utf-8'))
        if changed:
            staged[file] = updated.encode('utf-8')
    for newfile, content_file in [
        (destination, source_new),
        (root / 'tests' / 'test_fastpath.py', test_new),
    ]:
        payload = content_file.read_bytes()
        if not newfile.exists() or newfile.read_bytes() != payload:
            staged[newfile] = payload
    print(f"Destination: {root}")
    for path in staged:
        print('  UPDATE' if path.exists() else '  CREATE', path.relative_to(root))
    if args.dry_run:
        return 0
    backup = root / '.fastpath_backup' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if staged:
        for file in staged:
            if file.exists():
                saved = backup / file.relative_to(root)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, saved)
        for file, content in staged.items():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
    print(f"Applied {len(staged)} changes. Backups (if any): {backup}")
    print('Run: cd', root, "&& python -m unittest discover -s tests -p test_fastpath.py -v")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)
