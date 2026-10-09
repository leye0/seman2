"""Score coreference on novel sentences 1–10 against the gold chains.

Usage:
    python _coref_eval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, str(Path("data").resolve().parent))

from data.gold_coref_1_10 import GOLD_CHAINS, GOLD_SINGLETONS  # noqa: E402
from seman_parser.coverage import extract_sentences  # noqa: E402
from seman_parser.coref_eval import evaluate  # noqa: E402
from seman_parser.reader import DiscourseProcessor  # noqa: E402


def main() -> int:
    cases = extract_sentences(Path("../data/the_map_of_everything_nlp_novel.txt"), limit=10)
    texts = [c.text for c in cases]
    print(f"sentences ({len(texts)}):")
    for c in cases:
        print(f"  {c.index:2d}. {c.text}")

    proc = DiscourseProcessor.from_dir("data")
    report = proc.read_many(texts)

    # mention_id -> entity_id after link_best
    entity_of: dict[str, str] = {}
    for eid, ent in report.state.entities.items():
        for mid in ent.mentions:
            entity_of[mid] = eid

    print("\n=== system chains (multi-mention) ===")
    for eid, surfaces in report.entity_chains().items():
        if len(surfaces) >= 2:
            print(f"  {eid}: {surfaces}")

    mentions = [m for s in report.sentences for m in s.mentions]

    print("\n=== B3 / LEA on gold chains ===")
    ev = evaluate(GOLD_CHAINS, mentions, entity_of)
    print(ev.summary())

    print("\n=== including singletons ===")
    allg = dict(GOLD_CHAINS)
    allg.update(GOLD_SINGLETONS)
    ev2 = evaluate(allg, mentions, entity_of)
    print(ev2.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
