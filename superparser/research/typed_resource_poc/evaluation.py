"""Auditable external gold-standard evaluation: UD English-EWT TEST only.

The POC learns lexical evidence exclusively from UD-EWT TRAIN, never the test
set or the Novel cases. Stanza models are external pretrained taggers/parsers.
Metrics are strictly aligned by ID and token surface; no silent exclusions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .core import Word, grammatical_observations, validate_dependency_tree


@dataclass(frozen=True)
class GoldSentence:
    sent_id: str
    tokens: tuple[Word, ...]
    text: str


def read_conllu(conllu: str) -> list[GoldSentence]:
    sentences: list[GoldSentence] = []
    sent_id = ""
    text = ""
    words: list[Word] = []

    def save() -> None:
        if not words:
            return
        good, reason = validate_dependency_tree(words)
        if not good:
            raise ValueError(f"Invalid UD gold tree {sent_id}: {reason}")
        sentences.append(GoldSentence(sent_id, tuple(words), text))

    for line in (conllu.rstrip() + "\n\n").splitlines():
        if not line.strip():
            save()
            sent_id = ""
            text = ""
            words = []
            continue
        if line.startswith("# sent_id ="):
            sent_id = line.partition("=")[2].strip()
        elif line.startswith("# text ="):
            text = line.partition("=")[2].strip()
        elif line.startswith("#"):
            continue
        else:
            cells = line.split("\t")
            if len(cells) != 10:
                raise ValueError(f"Bad CoNLL-U data: {line[:75]}")
            if not cells[0].isdigit():  # Skip multiword lines and empty nodes.
                continue
            if not cells[6].isdigit():
                raise ValueError(f"Gold head not numeric for {sent_id}: {line}")
            words.append(Word(id=int(cells[0]), text=cells[1],
                              lemma=cells[2].lower(), upos=cells[3],
                              head=int(cells[6]), deprel=cells[7],
                              features=cells[5]))
    return sentences


def observation_keys(words: Sequence[Word]) -> set[tuple[str, int, int]]:
    return {(o["kind"], o["head_id"], o["dependent_id"])
            for o in grammatical_observations(list(words))}


def compare_to_gold(gold: Sequence[GoldSentence], predictions: Sequence[Sequence[Word]]) -> dict[str, Any]:
    """Evaluate on every gold token, including failed or misaligned sentences.

    No sentence is dropped when the tokenizer misses a gold word. In this
    experiment *gold tokenization is supplied* to Stanza, so segmentation
    errors are deliberately outside the scope of this primary evaluation.
    """
    if len(gold) != len(predictions):
        raise ValueError("Predictions must include every held-out gold sentence")
    counts = Counter()
    per_kind: dict[str, Counter] = {}
    failures: list[dict[str, Any]] = []
    for expected, predicted in zip(gold, predictions):
        g = list(expected.tokens)
        p = list(predicted)
        counts["gold_sentences"] += 1
        counts["gold_tokens"] += len(g)
        counts["gold_nonpunct_tokens"] += sum(w.upos != "PUNCT" for w in g)
        aligned = len(g) == len(p) and all(
            (a.id, a.text) == (b.id, b.text) for a, b in zip(g, p))
        counts["aligned_sentences"] += int(aligned)
        if not aligned:
            counts["unaligned_sentences"] += 1
            counts["unaligned_gold_tokens"] += len(g)
            if len(failures) < 20:
                failures.append({"sent_id": expected.sent_id,
                                 "gold": [w.text for w in g],
                                 "predicted": [w.text for w in p]})
        # Gold syntactic relations contribute to recall even for unaligned input.
        gold_keys = observation_keys(g)
        predicted_keys = observation_keys(p) if aligned else set()
        for kind in sorted(set(k for k,_,_ in gold_keys | predicted_keys)):
            stats = per_kind.setdefault(kind, Counter())
            gset = {x for x in gold_keys if x[0] == kind}
            pset = {x for x in predicted_keys if x[0] == kind}
            stats["gold"] += len(gset)
            stats["predicted"] += len(pset)
            stats["correct"] += len(gset & pset)
        if not aligned:
            continue
        counts["aligned_gold_tokens"] += len(g)
        for gw, pw in zip(g, p):
            if gw.upos == pw.upos:
                counts["upos_correct"] += 1
            counts["uas_correct"] += int(gw.head == pw.head)
            counts["las_correct"] += int(gw.head == pw.head and gw.deprel == pw.deprel)
            if gw.upos != "PUNCT":
                counts["uas_nonpunct_correct"] += int(gw.head == pw.head)
                counts["las_nonpunct_correct"] += int(gw.head == pw.head and gw.deprel == pw.deprel)

    def ratio(num: int, den: int) -> float | None:
        return round(num/den, 6) if den else None

    return {
        "counts": dict(counts),
        "metrics": {
            "strict_uas_all": ratio(counts["uas_correct"], counts["gold_tokens"]),
            "strict_las_all": ratio(counts["las_correct"], counts["gold_tokens"]),
            "strict_upos_all": ratio(counts["upos_correct"], counts["gold_tokens"]),
            "strict_uas_no_punct": ratio(counts["uas_nonpunct_correct"], counts["gold_nonpunct_tokens"]),
            "strict_las_no_punct": ratio(counts["las_nonpunct_correct"], counts["gold_nonpunct_tokens"]),
            "alignment_rate": ratio(counts["aligned_sentences"], counts["gold_sentences"]),
        },
        "adjectival_relations": {
            kind: {
                **dict(c),
                "precision": ratio(c["correct"], c["predicted"]),
                "recall": ratio(c["correct"], c["gold"]),
                "f1": ratio(2*c["correct"], c["gold"] + c["predicted"]),
            }
            for kind,c in sorted(per_kind.items())
        },
        "alignment_failures": failures,
        "conditions": {
            "gold_tokens_supplied": True,
            "gold_pos_supplied": False,
            "gold_heads_or_labels_supplied": False,
            "gold_lemmas_supplied": False,
            "unmatched_gold_tokens_count_as_errors": True,
            "test_data_used_for_lexical_induction": False,
        },
    }
