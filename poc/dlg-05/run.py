#!/usr/bin/env python3
"""DLG-05: attributed SDRT relation graphs from the official DISRPT release."""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
REPO = ROOT / ".local/share/disrpt-latest"
OUT = P / "output"
SELECTIONS = (
    {"dataset": "eng.sdrt.stac", "split": "dev", "doc": "pilot20", "language": "en",
     "genre": "multiparty strategic chat", "license": "CC BY-NC-SA 4.0"},
    {"dataset": "fra.sdrt.annodis", "split": "dev", "doc": "news_32_28-01-2003", "language": "fr",
     "genre": "written news", "license": "CC BY-NC-SA 3.0"},
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def token_indexes(spec: str) -> list[int]:
    indexes = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            indexes.extend(range(lo, hi + 1))
        else:
            indexes.append(int(part))
    return indexes


def read_conllu(path: Path, wanted_doc: str) -> tuple[dict[int, dict], list[dict]]:
    tokens: dict[int, dict] = {}
    sentences = []
    current_doc = None
    metadata: dict[str, str] = {}
    rows: list[list[str]] = []
    doc_index = 0

    def flush() -> None:
        nonlocal doc_index, metadata, rows
        if not rows:
            metadata = {}
            return
        if current_doc == wanted_doc:
            sent_token_ids = []
            for cols in rows:
                if "-" in cols[0] or "." in cols[0]:
                    continue
                doc_index += 1
                misc = dict(item.split("=", 1) for item in cols[9].split("|") if "=" in item)
                tokens[doc_index] = {
                    "index": doc_index, "form": cols[1], "lemma": cols[2], "upos": cols[3],
                    "sentence_id": metadata.get("sent_id"), "speaker": metadata.get("speaker"),
                    "segment_start": misc.get("Seg") == "B-seg",
                }
                sent_token_ids.append(doc_index)
            sentences.append({"id": metadata.get("sent_id"), "speaker": metadata.get("speaker"),
                              "text": metadata.get("text"), "token_indexes": sent_token_ids})
        metadata = {}
        rows = []

    for line in path.read_text().splitlines() + [""]:
        if not line:
            flush()
        elif line.startswith("# "):
            key, sep, value = line[2:].partition(" = ")
            if sep:
                if key == "newdoc_id":
                    flush()
                    current_doc = value
                    doc_index = 0
                metadata[key] = value
        elif not line.startswith("#"):
            rows.append(line.split("\t"))
    cursor = 0
    for token in tokens.values():
        token["char_span_in_reconstructed_text"] = [cursor, cursor + len(token["form"])]
        cursor += len(token["form"]) + 1
    return tokens, sentences


def crossing_pairs(relations: list[dict], order: dict[str, int]) -> list[list[str]]:
    intervals = []
    for rel in relations:
        a, b = sorted((order[rel["unit1"]], order[rel["unit2"]]))
        if a != b:
            intervals.append((a, b, rel["id"]))
    crossings = []
    for i, (a, b, rid1) in enumerate(intervals):
        for c, d, rid2 in intervals[i + 1:]:
            if (a < c < b < d) or (c < a < d < b):
                crossings.append([rid1, rid2])
    return crossings


def build(selection: dict) -> dict:
    dataset = selection["dataset"]
    stem = f"{dataset}_{selection['split']}"
    base = REPO / "data" / dataset
    rel_path, conllu_path = base / f"{stem}.rels", base / f"{stem}.conllu"
    tokens, sentences = read_conllu(conllu_path, selection["doc"])
    with rel_path.open(newline="") as handle:
        rows = [row for row in csv.DictReader(handle, delimiter="\t") if row["doc"] == selection["doc"]]
    if not rows or not tokens:
        raise ValueError(f"No data for {dataset}/{selection['doc']}")

    unit_specs: dict[tuple[str, str], dict] = {}
    for row in rows:
        for side in ("1", "2"):
            spec, text = row[f"unit{side}_toks"], row[f"unit{side}_txt"]
            key = (spec, text)
            unit_specs.setdefault(key, {"token_spec": spec, "text": text})
    sorted_specs = sorted(unit_specs.values(), key=lambda u: (min(token_indexes(u["token_spec"])), token_indexes(u["token_spec"])))
    units = []
    key_to_id = {}
    for ordinal, unit in enumerate(sorted_specs):
        indexes = token_indexes(unit["token_spec"])
        unresolved = [i for i in indexes if i not in tokens]
        token_rows = [tokens[i] for i in indexes if i in tokens]
        resolved_text = " ".join(t["form"] for t in token_rows)
        char_spans = []
        for part in unit["token_spec"].split(","):
            part_indexes = token_indexes(part)
            if all(i in tokens for i in part_indexes):
                char_spans.append([tokens[part_indexes[0]]["char_span_in_reconstructed_text"][0],
                                   tokens[part_indexes[-1]]["char_span_in_reconstructed_text"][1]])
        uid = f"{selection['doc']}:edu:{ordinal + 1}"
        key_to_id[(unit["token_spec"], unit["text"])] = uid
        units.append({
            "id": uid, "ordinal": ordinal, "token_spans": unit["token_spec"].split(","),
            "token_indexes": indexes, "text": unit["text"],
            "resolved_syntactic_text": resolved_text,
            "text_matches_resolved_tokens": resolved_text == unit["text"].replace(" <*> ", " "),
            "char_spans_in_reconstructed_text": char_spans,
            "raw_text": next((r[f"u{s}_raw"] for r in rows for s in ("1", "2")
                              if r[f"unit{s}_toks"] == unit["token_spec"] and r[f"unit{s}_txt"] == unit["text"]), unit["text"]),
            "sentence_ids": list(dict.fromkeys(t["sentence_id"] for t in token_rows)),
            "speakers": list(dict.fromkeys(t["speaker"] for t in token_rows if t["speaker"])),
            "discontinuous": len(unit["token_spec"].split(",")) > 1,
            "all_token_indexes_resolved": not unresolved,
        })
    unit_by_id = {u["id"]: u for u in units}
    order = {u["id"]: u["ordinal"] for u in units}

    relations = []
    graph = nx.MultiDiGraph(document=selection["doc"], formalism="SDRT")
    for unit in units:
        graph.add_node(unit["id"], **{k: v for k, v in unit.items() if k != "id"})
    for number, row in enumerate(rows, 1):
        u1 = key_to_id[(row["unit1_toks"], row["unit1_txt"])]
        u2 = key_to_id[(row["unit2_toks"], row["unit2_txt"])]
        source, target = (u1, u2) if row["dir"] == "1>2" else (u2, u1)
        rel = {
            "id": f"{selection['doc']}:rel:{number}", "unit1": u1, "unit2": u2,
            "source": source, "target": target, "direction": row["dir"],
            "label": row["label"], "original_label": row["orig_label"],
            "relation_type": row["rel_type"],
            "nonlocal": abs(order[u1] - order[u2]) > 1,
            "cross_turn": set(unit_by_id[u1]["sentence_ids"]) != set(unit_by_id[u2]["sentence_ids"]),
            "cross_speaker": bool(unit_by_id[u1]["speakers"] and unit_by_id[u2]["speakers"] and
                                  set(unit_by_id[u1]["speakers"]) != set(unit_by_id[u2]["speakers"])),
            "raw_disrpt_row": row,
        }
        relations.append(rel)
        graph.add_edge(source, target, key=rel["id"], relation_id=rel["id"], label=rel["label"])
    crossings = crossing_pairs(relations, order)
    weak_components = [sorted(component, key=order.get) for component in nx.weakly_connected_components(graph)]
    graph_data = nx.node_link_data(graph, edges="edges")
    result = {
        "document": selection,
        "provenance": {
            "producer": "DISRPT/latest", "formalism": "SDRT", "repository": "https://github.com/disrpt/latest",
            "commit": subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
            "relation_file": str(rel_path.relative_to(REPO)), "relation_file_sha256": sha256(rel_path),
            "conllu_file": str(conllu_path.relative_to(REPO)), "conllu_file_sha256": sha256(conllu_path),
            "annotation_kind": "manual gold converted to DISRPT uniform format",
        },
        "reconstructed_syntactic_text": " ".join(token["form"] for token in tokens.values()),
        "sentences_or_turns": sentences, "tokens": list(tokens.values()), "discourse_units": units,
        "relations": relations, "thread_components": weak_components,
        "thread_structure": {"annotated_thread_ids_available": False,
                             "derived_method": "weakly connected components of the gold relation graph",
                             "derived_components": weak_components},
        "crossing_relation_pairs": crossings, "networkx_node_link_graph": graph_data,
        "validation": {
            "all_unit_tokens_resolved": all(u["all_token_indexes_resolved"] for u in units),
            "all_unit_texts_match_resolved_tokens": all(u["text_matches_resolved_tokens"] for u in units),
            "all_units_have_expected_char_span_count": all(
                len(u["char_spans_in_reconstructed_text"]) == len(u["token_spans"]) for u in units),
            "node_count_matches": graph.number_of_nodes() == len(units),
            "edge_count_matches": graph.number_of_edges() == len(relations),
            "directed_acyclic": nx.is_directed_acyclic_graph(nx.DiGraph(graph)),
            "multi_parent_unit_count": sum(graph.in_degree(n) > 1 for n in graph.nodes),
            "nonlocal_relation_count": sum(r["nonlocal"] for r in relations),
            "cross_turn_relation_count": sum(r["cross_turn"] for r in relations),
            "cross_speaker_relation_count": sum(r["cross_speaker"] for r in relations),
            "crossing_pair_count": len(crossings),
        },
    }
    assert result["validation"]["all_unit_tokens_resolved"]
    assert result["validation"]["all_unit_texts_match_resolved_tokens"]
    assert result["validation"]["all_units_have_expected_char_span_count"]
    assert result["validation"]["node_count_matches"] and result["validation"]["edge_count_matches"]
    return result


def main() -> None:
    if not (REPO / ".git").is_dir():
        raise SystemExit("Missing .local/share/disrpt-latest; clone https://github.com/disrpt/latest.git")
    results = [build(selection) for selection in SELECTIONS]
    english, french = results
    summary = {
        "documents": len(results), "languages": [r["document"]["language"] for r in results],
        "units": sum(len(r["discourse_units"]) for r in results),
        "relations": sum(len(r["relations"]) for r in results),
        "stac_speakers": sorted({speaker for u in english["discourse_units"] for speaker in u["speakers"]}),
        "nonlocal_relations": sum(r["validation"]["nonlocal_relation_count"] for r in results),
        "cross_turn_relations": sum(r["validation"]["cross_turn_relation_count"] for r in results),
        "cross_speaker_relations": sum(r["validation"]["cross_speaker_relation_count"] for r in results),
        "crossing_relation_pairs": sum(r["validation"]["crossing_pair_count"] for r in results),
        "discontinuous_french_units": sum(u["discontinuous"] for u in french["discourse_units"]),
        "all_unit_texts_and_spans_validated": all(
            r["validation"]["all_unit_texts_match_resolved_tokens"] and
            r["validation"]["all_units_have_expected_char_span_count"] for r in results),
        "gold_thread_ids_available": False,
        "thread_components_are_derived": True,
        "comparison_with_disc_01_02": {
            "sdrt": "directed labelled graph; nonlocal, crossing, multi-parent and cross-turn links are permitted",
            "rst_erst": "DISC-01/02 exposes a rooted binary constituency tree; extra eRST graph layers were absent",
            "must_not_collapse": True,
        },
        "automatic_general_sdrt_parser_available": False,
        "verdict": "GO_ATTRIBUTED_SDRT_GRAPH_IMPORT_ONLY",
    }
    assert summary["nonlocal_relations"] and summary["cross_turn_relations"] and len(summary["stac_speakers"]) > 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "networkx": importlib.metadata.version("networkx"),
        "disrpt_commit": results[0]["provenance"]["commit"], "selections": SELECTIONS,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"DLG-05: {summary['units']} units/{summary['relations']} relations; "
          f"{summary['nonlocal_relations']} non-local, {summary['cross_turn_relations']} cross-turn; graph import GO")


if __name__ == "__main__":
    main()
