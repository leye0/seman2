#!/usr/bin/env python3
"""DLG-04: lossless DiAML XML import plus an explicitly attributed view."""
from __future__ import annotations

import hashlib
import json
import platform
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parent.parent
DATA = ROOT / ".local/share/dialogbank"
OUT = P / "output"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
SOURCES = {
    "trains1.diaml": "https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2022/04/trains1.diaml",
    "trains2.diaml": "https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2022/04/trains2.diaml",
    "trains3.diaml": "https://dialogbank.lsv.uni-saarland.de/wp-content/uploads/2022/04/trains3.diaml",
}


def local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def node_to_data(node: ET.Element) -> dict:
    """Generic tree encoding: expanded names, attributes, text, tails and order."""
    return {
        "tag": node.tag,
        "attributes": dict(node.attrib),
        "text": node.text,
        "tail": node.tail,
        "children": [node_to_data(child) for child in node],
    }


def data_to_node(data: dict) -> ET.Element:
    node = ET.Element(data["tag"], data["attributes"])
    node.text = data["text"]
    node.tail = data["tail"]
    node.extend(data_to_node(child) for child in data["children"])
    return node


def signature(node: ET.Element):
    return (
        node.tag,
        tuple(node.attrib.items()),
        node.text,
        node.tail,
        tuple(signature(child) for child in node),
    )


def strip_ref(value: str | None) -> str | None:
    return value[1:] if value and value.startswith("#") else value


def ref_list(value: str) -> list[str]:
    return [strip_ref(item) for item in value.split()]


def import_file(path: Path) -> dict:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    generic = node_to_data(root)
    rebuilt = data_to_node(generic)
    roundtrip_equal = signature(root) == signature(rebuilt)
    serialized_rebuilt = ET.tostring(rebuilt, encoding="utf-8", xml_declaration=True)
    serialized_roundtrip_equal = signature(root) == signature(ET.fromstring(serialized_rebuilt))

    words = []
    cursor = 0
    for order, word in enumerate(e for e in root.iter() if local(e.tag) == "w"):
        token = word.text or ""
        start = cursor
        end = start + len(token)
        words.append({"id": word.attrib[XML_ID], "order": order, "text": token,
                      "char_span_in_reconstructed_text": [start, end]})
        cursor = end + 1
    word_by_id = {word["id"]: word for word in words}

    span_groups = {}
    for group in (e for e in root.iter() if local(e.tag) == "spanGrp"):
        gid = group.attrib[XML_ID]
        refs = [strip_ref(span.attrib.get("from")) for span in group if local(span.tag) == "span"]
        span_groups[gid] = refs

    segments = {}
    for fs in (e for e in root.iter() if local(e.tag) == "fs"):
        if fs.attrib.get("type") != "functionalSegment":
            continue
        sid = fs.attrib[XML_ID]
        component = next((strip_ref(f.attrib.get("fVal")) for f in fs if f.attrib.get("name") == "verbalComponent"), None)
        refs = span_groups.get(component, [])
        token_rows = [word_by_id[ref] for ref in refs if ref in word_by_id]
        segments[sid] = {
            "id": sid,
            "verbal_component": component,
            "token_refs": refs,
            "text": " ".join(row["text"] for row in token_rows),
            "token_order_span": [min((r["order"] for r in token_rows), default=None),
                                 max((r["order"] for r in token_rows), default=None)],
            "all_token_refs_resolved": len(token_rows) == len(refs),
        }

    standard = {XML_ID, "target", "sender", "addressee", "dimension", "communicativeFunction"}
    acts = []
    for act in (e for e in root.iter() if local(e.tag) == "dialogueAct"):
        target = strip_ref(act.attrib["target"])
        dependencies = {k: ref_list(v) for k, v in act.attrib.items() if k.endswith("Dependence")}
        qualifiers = {k: v for k, v in act.attrib.items() if k not in standard and not k.endswith("Dependence")}
        acts.append({
            "id": act.attrib[XML_ID], "target": target,
            "functional_segment": segments.get(target),
            "sender": strip_ref(act.attrib["sender"]),
            "addressee": strip_ref(act.attrib["addressee"]),
            "dimension": act.attrib["dimension"],
            "communicative_function": act.attrib["communicativeFunction"],
            "dependencies": dependencies, "qualifiers": qualifiers,
            "raw_attributes": dict(act.attrib),
        })
    act_ids = {act["id"] for act in acts}
    rhetorical = []
    for link in (e for e in root.iter() if local(e.tag) == "rhetoricalLink"):
        rhetorical.append({
            "dialogue_act": strip_ref(link.attrib.get("dact")),
            "antecedent": strip_ref(link.attrib.get("rhetoAntecedent")),
            "relation": link.attrib.get("rhetoRel"),
            "raw_attributes": dict(link.attrib),
        })
    target_counts = Counter(act["target"] for act in acts)
    dependency_targets = [target for act in acts for targets in act["dependencies"].values() for target in targets]
    participants = [e.attrib[XML_ID] for e in root.iter() if local(e.tag) == "particDescr"]
    participant_refs = [value for act in acts for value in (act["sender"], act["addressee"])]
    result = {
        "document_id": path.stem,
        "provenance": {"producer": "DialogBank", "formalism": "ISO_24617-2_DiAML",
                       "source_url": SOURCES[path.name], "sha256": hashlib.sha256(raw).hexdigest()},
        "participants": participants,
        "reconstructed_text": " ".join(word["text"] for word in words),
        "tokens": words, "functional_segments": list(segments.values()),
        "dialogue_acts": acts, "rhetorical_links": rhetorical,
        "losslessness": {
            "generic_xml_tree_roundtrip_equal": roundtrip_equal,
            "serialized_xml_roundtrip_equal": serialized_roundtrip_equal,
            "all_act_targets_resolved": all(act["functional_segment"] for act in acts),
            "all_functional_segment_token_refs_resolved": all(s["all_token_refs_resolved"] for s in segments.values()),
            "all_participant_refs_resolved": all(ref in participants for ref in participant_refs),
            "all_dependency_targets_resolved": all(target in act_ids for target in dependency_targets),
            "all_rhetorical_targets_resolved": all(
                link[side] in act_ids for link in rhetorical for side in ("dialogue_act", "antecedent")),
            "raw_xml_sha256": hashlib.sha256(raw).hexdigest(),
            "generic_xml_tree": generic,
        },
        "coverage": {
            "dimensions": sorted({act["dimension"] for act in acts}),
            "communicative_functions": sorted({act["communicative_function"] for act in acts}),
            "qualifier_names": sorted({key for act in acts for key in act["qualifiers"]}),
            "dependency_types": sorted({key for act in acts for key in act["dependencies"]}),
            "simultaneously_annotated_segment_count": sum(n > 1 for n in target_counts.values()),
        },
    }
    assert all(result["losslessness"][key] for key in (
        "generic_xml_tree_roundtrip_equal", "serialized_xml_roundtrip_equal", "all_act_targets_resolved",
        "all_functional_segment_token_refs_resolved", "all_participant_refs_resolved",
        "all_dependency_targets_resolved", "all_rhetorical_targets_resolved"))
    return result


def main() -> None:
    missing = [name for name in SOURCES if not (DATA / name).is_file()]
    if missing:
        raise SystemExit(f"Missing DialogBank resources: {', '.join(missing)}; see README.md")
    results = [import_file(DATA / name) for name in SOURCES]
    summary = {
        "document_count": len(results),
        "token_count": sum(len(r["tokens"]) for r in results),
        "functional_segment_count": sum(len(r["functional_segments"]) for r in results),
        "dialogue_act_count": sum(len(r["dialogue_acts"]) for r in results),
        "rhetorical_link_count": sum(len(r["rhetorical_links"]) for r in results),
        "dimensions": sorted({x for r in results for x in r["coverage"]["dimensions"]}),
        "qualifiers": sorted({x for r in results for x in r["coverage"]["qualifier_names"]}),
        "dependency_types": sorted({x for r in results for x in r["coverage"]["dependency_types"]}),
        "simultaneously_annotated_segment_count": sum(r["coverage"]["simultaneously_annotated_segment_count"] for r in results),
        "formalism_available": True,
        "reference_annotations_available": True,
        "automatic_analyzer_available": False,
        "verdict": "GO_LOSSLESS_REFERENCE_ANNOTATION_IMPORT_ONLY",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    (OUT / "versions-and-parameters.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
        "python": platform.python_version(), "xml_parser": "xml.etree.ElementTree",
        "dialogbank_page": "https://dialogbank.lsv.uni-saarland.de/?page_id=280",
        "source_files": SOURCES,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"DLG-04: {summary['dialogue_act_count']} acts, {len(summary['dimensions'])} dimensions, "
          f"{summary['simultaneously_annotated_segment_count']} multi-annotated segments; lossless import GO")


if __name__ == "__main__":
    main()
