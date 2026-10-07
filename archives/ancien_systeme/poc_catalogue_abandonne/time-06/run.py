#!/usr/bin/env python3
"""TIME-06: relational episodic retrieval before optional clock enrichment."""

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

POC_DIR = Path(__file__).resolve().parent
OUTPUT = POC_DIR / "output"


def retrieve(fixture, include_anchors):
    graph = nx.MultiDiGraph()
    order = nx.DiGraph()
    labels = {episode["id"]: episode["label"] for episode in fixture["episodes"]}
    order.add_nodes_from(labels)
    for transmission in fixture["transmissions"]:
        graph.add_edge(transmission["content"], transmission["id"], relation="content_of")
        graph.add_edge(transmission["id"], transmission["episode"], relation="contained_in")
    for item in fixture["relations"]:
        graph.add_edge(item["left"], item["right"], relation=item["relation"])
        if item["relation"] == "before":
            order.add_edge(item["left"], item["right"])
    closure = nx.transitive_closure_dag(order)
    transmission = next(item for item in fixture["transmissions"] if item["content"] == fixture["query"]["content"])
    episode = transmission["episode"]
    after = sorted(node for node in closure.predecessors(episode))
    before = sorted(node for node in closure.successors(episode))
    relational = {
        "path": [fixture["query"]["content"], transmission["id"], episode],
        "episode": episode, "after": after, "before": before,
        "answer": " et ".join(
            (["après " + ", ".join(labels[node] for node in after)] if after else [])
            + (["avant " + ", ".join(labels[node] for node in before)] if before else [])
        ) or "position relationnelle insuffisamment contrainte",
        "uncertainty": "partial" if not after or not before else "bounded",
    }
    anchors = [anchor for anchor in fixture["anchors"] if anchor["target"] == transmission["id"]] if include_anchors else []
    return {"relational_answer": relational, "optional_external_anchor_enrichment": anchors}


def main():
    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    results = []
    for fixture in fixtures:
        without = retrieve(fixture, False)
        with_anchors = retrieve(fixture, True)
        oracle = fixture["oracle"]
        answer = without["relational_answer"]
        assert answer["path"][1:] == [oracle["transmission"], oracle["episode"]]
        assert answer["after"] == oracle["after"] and answer["before"] == oracle["before"]
        assert answer == with_anchors["relational_answer"]
        results.append({"fixture_id": fixture["id"], "without_anchors": without, "with_anchors": with_anchors, "relational_answer_invariant": True})
    summary = {
        "fixture_count": len(results), "relational_answers": len(results),
        "calendar_enrichments": sum(bool(r["with_anchors"]["optional_external_anchor_enrichment"]) for r in results),
        "anchor_removal_changed_relational_answer": 0,
        "verdict": "GO_EPISODIC_RELATIONAL_RETRIEVAL_BEFORE_CLOCK_ENRICHMENT",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, value in (("results.json", results), ("summary.json", summary), ("versions-and-parameters.json", {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "networkx": nx.__version__, "retrieval_policy": "content to transmission to episode to relational bounds; anchors optional last"})):
        (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TIME-06: {len(results)} relational answers; {summary['calendar_enrichments']} optional clock enrichment")


if __name__ == "__main__":
    main()
