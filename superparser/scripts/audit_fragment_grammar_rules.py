"""Review possibly over-permissive grammatical rules without deleting any.

The rule inventory is intentionally *not* an assertion that candidates are bad:
English has valid ellipsis, imperatives, valedictions, gapping and dialogue.
The audit identifies root productions that need source-context and negative
contrast review after segmentation is corrected. Only a selected-tree proof
can justify changing a rule.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
CURRENT = ROOT / "data" / "grammar.jsonl"
BASELINE = REPO / "docs" / "GRAMMAR_RULE_IDS_2026_10_11.json"
PREDICATE_CATEGORIES = frozenset({
    "VP", "VP-NP", "VP-GAP", "CLAUSE", "WH-CLAUSE", "DIRECT-SPEECH",
    "AUX", "AUX-BE", "MODAL", "COPULA", "V",
})


def classify_rule(rule: dict) -> tuple[str, ...]:
    """Return review flags, not evidence that a sentence was falsely accepted."""
    lhs = rule["lhs"]["category"]
    rhs = [entry["category"] for entry in rule["rhs"]]
    flags = []
    if lhs == "CLAUSE" and not any(
        cat in PREDICATE_CATEGORIES or cat.startswith("V-") for cat in rhs
    ):
        flags.append("clause_without_overt_predicate")
    if re.search(
        r"ellips|gapping|fragment",
        rule["id"] + " " + json.dumps(rule.get("provenance", {})),
        flags=re.IGNORECASE,
    ):
        flags.append("ellipsis_or_fragment_license")
    if lhs == "CLAUSE" and rhs and rhs[0] == "COORD":
        flags.append("root_started_by_coordinator")
    if lhs == "CLAUSE" and rhs and rhs[0] in ("NP", "PP", "ADVP") and (
        "VP" not in rhs and "CLAUSE" not in rhs
    ):
        flags.append("nonstandard_root_without_finite_vp")
    return tuple(sorted(set(flags)))


def analyze(
    rules: list[dict],
    prior_ids: set[str],
    *, prior_commit: str,
) -> dict:
    if len({r["id"] for r in rules}) != len(rules):
        raise ValueError("Duplicate grammar rule IDs")
    now = {r["id"] for r in rules}
    candidates = []
    for rule in rules:
        flags = classify_rule(rule)
        if not flags:
            continue
        candidates.append({
            "id": rule["id"],
            "introduced_after_baseline": rule["id"] not in prior_ids,
            "lhs": rule["lhs"]["category"],
            "rhs": [entry["category"] for entry in rule["rhs"]],
            "review_flags": list(flags),
            "has_provenance": bool(rule.get("provenance")),
        })
    candidates.sort(key=lambda c: (not c["introduced_after_baseline"],
                                  c["id"]))
    by_flag = Counter(flag for c in candidates for flag in c["review_flags"])
    return {
        "schema": "seman2-fragment-rule-review-v1",
        "baseline_commit": prior_commit,
        "baseline_count": len(prior_ids),
        "current_count": len(rules),
        "rules_added_since_baseline": len(now - prior_ids),
        "rules_removed_since_baseline": len(prior_ids - now),
        "requires_ranking_tree_ablation_before_deletion": True,
        "suspect_count_is_not_confirmed_false_positives": True,
        "review_candidate_count": len(candidates),
        "review_flags": dict(sorted(by_flag.items())),
        "candidates": candidates,
    }


def render_markdown(data: dict) -> str:
    lines = [
        "# Audit des règles grammaticales potentiellement trop permissives",
        "",
        "Cet audit **ne confirme aucune mauvaise règle** : il identifie des",
        "productions à inspecter dans leurs arbres de rang 1 et avec des tests",
        "positifs et négatifs. L'ellipse et les phrases sans verbe peuvent être",
        "légitimes. **Aucune règle n'est supprimée automatiquement.**",
        "",
        f"- Référence du {data['baseline_commit'][:12]} : "
        f"{data['baseline_count']} règles.",
        f"- Grammaire actuelle : {data['current_count']} règles "
        f"({data['rules_added_since_baseline']} nouveaux IDs, "
        f"{data['rules_removed_since_baseline']} IDs disparus).",
        f"- À examiner structurellement : {data['review_candidate_count']} "
        "règles (signalement statique, non un verdict).",
        "",
        "| Règle | Introduite après référence ? | Tête → membres | Signaux |",
        "|---|---|---|---|",
    ]
    for x in data["candidates"]:
        lines.append(
            "| " + x["id"] + " | " +
            ("oui" if x["introduced_after_baseline"] else "non") + " | " +
            x["lhs"] + " → " + " ".join(x["rhs"]) + " | " +
            ", ".join(x["review_flags"]) + " |"
        )
    lines.extend([
        "",
        "## Règle de suppression",
        "",
        "Pour retirer ou durcir une production, démontrer sur des passages sources",
        "complets que son arbre sélectionné accepte un fragment artificiel et",
        "qu'elle n'est pas nécessaire à des énoncés légitimes (dialogue,",
        "impératif, ellipse). Comparer les alternatives, 120 annotations",
        "structurelles et contrastes positifs/négatifs avant/après, ainsi que",
        "le même SHA de cohorte. L'audit seul ne permet aucune suppression.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--out-dir", type=Path)
    options = args.parse_args()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in CURRENT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = analyze(rows, set(baseline["rule_ids"]),
                     prior_commit=baseline["source_commit"])
    if options.out_dir is not None:
        options.out_dir.mkdir(parents=True, exist_ok=True)
        (options.out_dir / "fragment_grammar_rule_audit.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (options.out_dir / "fragment_grammar_rule_audit.md").write_text(
            render_markdown(result), encoding="utf-8",
        )
    print("FRAGMENT_GRAMMAR_RULE_AUDIT", json.dumps({
        k: v for k, v in result.items() if k != "candidates"
    }), flush=True)


if __name__ == "__main__":
    main()
