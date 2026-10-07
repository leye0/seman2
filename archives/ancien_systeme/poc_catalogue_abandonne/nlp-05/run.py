#!/usr/bin/env python3
"""Run NLP-05: inspect the structures emitted by Link Grammar."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import linkgrammar
from linkgrammar import Clinkgrammar as clg
from linkgrammar import Dictionary, ParseOptions, Sentence


POC_DIR = Path(__file__).resolve().parent
REPO_ROOT = POC_DIR.parents[1]
DEFAULT_LINK_PARSER = REPO_ROOT / ".local/bin/link-parser"
DEFAULT_MAX_LINKAGES = 100
DEFAULT_TIMEOUT_SECONDS = 10


def stable_id(prefix: str, payload: Any) -> str:
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return prefix + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def merged_spans(spans: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if start == end:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def source_partition(source: str, spans: list[list[int]]) -> dict[str, Any]:
    covered = merged_spans(spans)
    residuals = []
    cursor = 0
    for start, end in covered:
        if cursor < start:
            residuals.append(
                {"charspan": [cursor, start], "source_slice": source[cursor:start]}
            )
        cursor = end
    if cursor < len(source):
        residuals.append(
            {"charspan": [cursor, len(source)], "source_slice": source[cursor:]}
        )
    segments = [
        {"kind": "token", "charspan": span, "source_slice": source[slice(*span)]}
        for span in covered
    ] + [{"kind": "residual", **item} for item in residuals]
    segments.sort(key=lambda item: item["charspan"])
    return {
        "covered_charspans": covered,
        "residual_spans": residuals,
        "ordered_partition": segments,
        "reassembled_source": "".join(item["source_slice"] for item in segments),
        "source_text_preserved": (
            "".join(item["source_slice"] for item in segments) == source
        ),
    }


def parse_constituent_tree(
    bracketed: str, lexical_tokens: list[dict[str, Any]]
) -> dict[str, Any]:
    pieces = bracketed.replace("[", " [ ").replace("]", " ] ").split()
    position = 0
    terminal_position = 0

    def parse_node() -> dict[str, Any]:
        nonlocal position, terminal_position
        if pieces[position] != "[":
            raise ValueError("Expected opening bracket")
        position += 1
        category = pieces[position]
        position += 1
        children = []
        while True:
            if position >= len(pieces):
                raise ValueError("Unclosed constituent")
            if pieces[position] == category and pieces[position + 1] == "]":
                position += 2
                break
            if pieces[position] == "[":
                children.append(parse_node())
                continue
            if terminal_position >= len(lexical_tokens):
                raise ValueError("More terminals than linkage tokens")
            token = lexical_tokens[terminal_position]
            children.append(
                {
                    "kind": "terminal",
                    "tree_form": pieces[position],
                    "word_index": token["index"],
                    "linkage_form": token["form"],
                    "charspan": token["charspan"],
                    "source_slice": token["source_slice"],
                }
            )
            terminal_position += 1
            position += 1
        child_spans = [child["charspan"] for child in children if child["charspan"]]
        return {
            "kind": "constituent",
            "category": category,
            "children": children,
            "charspan": (
                [
                    min(span[0] for span in child_spans),
                    max(span[1] for span in child_spans),
                ]
                if child_spans
                else None
            ),
        }

    root = parse_node()
    if position != len(pieces):
        raise ValueError("Trailing constituent-tree data")
    if terminal_position != len(lexical_tokens):
        raise ValueError("Fewer terminals than linkage tokens")
    return root


def count_constituents(node: dict[str, Any]) -> int:
    if node["kind"] == "terminal":
        return 0
    return 1 + sum(count_constituents(child) for child in node["children"])


def build_options(
    max_linkages: int, timeout_seconds: int, max_null_count: int, islands_ok: bool
) -> ParseOptions:
    return ParseOptions(
        verbosity=0,
        linkage_limit=max_linkages,
        min_null_count=0,
        max_null_count=max_null_count,
        islands_ok=islands_ok,
        short_length=16,
        display_morphology=True,
        spell_guess=False,
        repeatable_rand=True,
        max_parse_time=timeout_seconds,
    )


def linkage_record(
    fixture: dict[str, Any], linkage: Any, rank: int, pass_name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = fixture["sentence"]
    tokens = []
    for index in range(linkage.num_of_words()):
        charspan = [
            linkage.word_char_start(index),
            linkage.word_char_end(index),
        ]
        bytespan = [
            linkage.word_byte_start(index),
            linkage.word_byte_end(index),
        ]
        boundary_wall = index in (0, linkage.num_of_words() - 1)
        tokens.append(
            {
                "index": index,
                "form": linkage.word(index),
                "boundary_wall": boundary_wall,
                "charspan": charspan,
                "bytespan": bytespan,
                "source_slice": source[slice(*charspan)],
                "disjunct": clg.linkage_get_disjunct_str(linkage._obj, index),
                "word_disjunct_cost": clg.linkage_get_disjunct_cost(
                    linkage._obj, index
                ),
            }
        )

    links = []
    for index, link in enumerate(linkage.links()):
        left_index = clg.linkage_get_link_lword(linkage._obj, index)
        right_index = clg.linkage_get_link_rword(linkage._obj, index)
        links.append(
            {
                "index": index,
                "type": clg.linkage_get_link_label(linkage._obj, index),
                "left": {
                    "word_index": left_index,
                    "form": tokens[left_index]["form"],
                    "connector": link.left_label,
                    "charspan": tokens[left_index]["charspan"],
                },
                "right": {
                    "word_index": right_index,
                    "form": tokens[right_index]["form"],
                    "connector": link.right_label,
                    "charspan": tokens[right_index]["charspan"],
                },
                "length": len(link),
                "direct_lnk": None,
                "derived_support_charspan": [
                    min(tokens[left_index]["charspan"][0], tokens[right_index]["charspan"][0]),
                    max(tokens[left_index]["charspan"][1], tokens[right_index]["charspan"][1]),
                ],
            }
        )

    bracketed_tree = linkage.constituent_tree(2)
    lexical_tokens = [token for token in tokens if not token["boundary_wall"]]
    structured_tree = parse_constituent_tree(bracketed_tree, lexical_tokens)
    costs = {
        "unused_word_cost": linkage.unused_word_cost(),
        "disjunct_cost": linkage.disjunct_cost(),
        "link_cost": linkage.link_cost(),
        "violation_name": linkage.violation_name(),
    }
    identity_payload = {
        "fixture": fixture["id"],
        "pass": pass_name,
        "rank": rank,
        "tokens": [
            [token["form"], token["charspan"], token["disjunct"]] for token in tokens
        ],
        "links": [
            [
                link["left"]["word_index"],
                link["type"],
                link["left"]["connector"],
                link["right"]["connector"],
                link["right"]["word_index"],
            ]
            for link in links
        ],
        "costs": costs,
        "constituent_tree": bracketed_tree,
    }
    linkage_id = stable_id("linkage:", identity_payload)
    record = {
        "linkage_id": linkage_id,
        "rank": rank,
        "pass": pass_name,
        "support": {"source_observation_id": f"source:{fixture['id']}"},
        "producer": {
            "parser": "Link Grammar",
            "dictionary_language": "en",
            "decoder": "Link Grammar Python bindings",
        },
        "is_full_parse": costs["unused_word_cost"] == 0,
        "costs": costs,
        "tokens": tokens,
        "source_coverage": source_partition(
            source, [token["charspan"] for token in lexical_tokens]
        ),
        "links": links,
        "constituency": {
            "available": True,
            "format": "Link Grammar constituent tree, mode 2",
            "bracketed": bracketed_tree,
            "structured": structured_tree,
            "constituent_count": count_constituents(structured_tree),
            "terminal_count": len(lexical_tokens),
        },
        "diagram": linkage.diagram(display_walls=True, screen_width=180),
    }
    native = {
        "fixture": fixture["id"],
        "pass": pass_name,
        "rank": rank,
        "linkage_id": linkage_id,
        "words": list(linkage.words()),
        "links": [str(link) for link in linkage.links()],
        "unused_word_cost": linkage.unused_word_cost(),
        "disjunct_cost": linkage.disjunct_cost(),
        "link_cost": linkage.link_cost(),
        "violation_name": linkage.violation_name(),
        "constituent_tree": bracketed_tree,
        "diagram": record["diagram"],
    }
    return record, native


def parse_pass(
    fixture: dict[str, Any],
    dictionary: Dictionary,
    max_linkages: int,
    timeout_seconds: int,
    max_null_count: int,
    islands_ok: bool,
    pass_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    options = build_options(
        max_linkages, timeout_seconds, max_null_count, islands_ok
    )
    sentence = Sentence(fixture["sentence"], dictionary, options)
    split_status = sentence.split()
    if split_status < 0:
        return (
            {
                "status": "split_failure",
                "split_status": split_status,
                "counts": {
                    "found_before_postprocessing": 0,
                    "postprocessed": 0,
                    "valid_returned": 0,
                },
                "sentence_null_count": None,
                "limit_reached_or_sampled": False,
                "linkages": [],
            },
            [],
        )
    parsed = sentence.parse()
    linkage_objects = list(parsed)
    records = []
    native = []
    for rank, linkage in enumerate(linkage_objects, start=1):
        record, raw_record = linkage_record(fixture, linkage, rank, pass_name)
        records.append(record)
        native.append(raw_record)
    found = clg.sentence_num_linkages_found(sentence._obj)
    postprocessed = clg.sentence_num_linkages_post_processed(sentence._obj)
    valid = len(records)
    return (
        {
            "status": "parsed" if records else "strict_parse_failure",
            "split_status": split_status,
            "counts": {
                "found_before_postprocessing": found,
                "postprocessed": postprocessed,
                "valid_returned": valid,
            },
            "sentence_null_count": sentence.null_count(),
            "limit_reached_or_sampled": found > postprocessed or valid >= max_linkages,
            "linkages": records,
        },
        native,
    )


def add_alternative_relations(parse_result: dict[str, Any]) -> None:
    linkages = parse_result["linkages"]
    if not linkages:
        return
    ids = [linkage["linkage_id"] for linkage in linkages]
    first = linkages[0]
    first_links = {
        (
            link["left"]["word_index"],
            link["type"],
            link["right"]["word_index"],
        )
        for link in first["links"]
    }
    for linkage in linkages:
        links = {
            (
                link["left"]["word_index"],
                link["type"],
                link["right"]["word_index"],
            )
            for link in linkage["links"]
        }
        linkage["competes_with"] = [item for item in ids if item != linkage["linkage_id"]]
        linkage["difference_from_rank_1"] = {
            "same_link_set": links == first_links,
            "added_links": sorted(links - first_links),
            "removed_links": sorted(first_links - links),
            "same_constituent_tree": (
                linkage["constituency"]["bracketed"]
                == first["constituency"]["bracketed"]
            ),
            "same_costs": linkage["costs"] == first["costs"],
        }


def validate(results: list[dict[str, Any]], max_linkages: int) -> None:
    expected_phenomena = {
        "simple",
        "ambiguous",
        "coordinated",
        "fragmentary",
        "ungrammatical",
    }
    if {result["phenomenon"] for result in results} != expected_phenomena:
        raise RuntimeError("NLP-05 fixture coverage changed")
    linkage_ids: set[str] = set()
    for result in results:
        strict = result["strict_parse"]
        if result["expected_status"] == "parsed":
            if strict["status"] != "parsed":
                raise RuntimeError(f"Expected parse failure: {result['id']}")
            if len(strict["linkages"]) < result["minimum_linkages"]:
                raise RuntimeError(f"Missing linkages: {result['id']}")
        elif strict["status"] != "strict_parse_failure" or strict["linkages"]:
            raise RuntimeError("Ungrammatical fixture did not fail strictly")
        if len(strict["linkages"]) > max_linkages:
            raise RuntimeError(f"Linkage limit exceeded: {result['id']}")
        for parse_result in [strict, result.get("null_link_recovery")]:
            if parse_result is None:
                continue
            for linkage in parse_result["linkages"]:
                if linkage["linkage_id"] in linkage_ids:
                    raise RuntimeError(f"Duplicate linkage id: {linkage['linkage_id']}")
                linkage_ids.add(linkage["linkage_id"])
                if not linkage["source_coverage"]["source_text_preserved"]:
                    raise RuntimeError(f"Source loss: {linkage['linkage_id']}")
                token_count = len(linkage["tokens"])
                for link in linkage["links"]:
                    if not link["type"]:
                        raise RuntimeError(f"Untyped link: {linkage['linkage_id']}")
                    for side in ("left", "right"):
                        if not 0 <= link[side]["word_index"] < token_count:
                            raise RuntimeError(f"Invalid endpoint: {linkage['linkage_id']}")
                constituency = linkage["constituency"]
                if not constituency["available"] or constituency["terminal_count"] != token_count - 2:
                    raise RuntimeError(f"Invalid constituents: {linkage['linkage_id']}")
    ambiguous = next(result for result in results if result["phenomenon"] == "ambiguous")
    distinct_trees = {
        linkage["constituency"]["bracketed"]
        for linkage in ambiguous["strict_parse"]["linkages"]
    }
    if len(distinct_trees) < ambiguous["minimum_distinct_constituent_trees"]:
        raise RuntimeError("Attachment ambiguity is not observable")
    observed_attachment_links = {
        (
            link["left"]["form"].split(".", 1)[0].lower(),
            link["type"],
            link["right"]["form"].split(".", 1)[0].lower(),
        )
        for linkage in ambiguous["strict_parse"]["linkages"]
        for link in linkage["links"]
    }
    if not all(
        tuple(required) in observed_attachment_links
        for required in ambiguous["required_attachment_links"]
    ):
        raise RuntimeError("Both PP attachment structures are not observable")
    ungrammatical = next(
        result for result in results if result["phenomenon"] == "ungrammatical"
    )
    recovery = ungrammatical["null_link_recovery"]
    if len(recovery["linkages"]) < ungrammatical["minimum_recovery_linkages"]:
        raise RuntimeError("Null-link recovery is not observable")
    if not all(not linkage["is_full_parse"] for linkage in recovery["linkages"]):
        raise RuntimeError("Recovery linkage mislabeled as full parse")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-linkages", type=int, default=DEFAULT_MAX_LINKAGES)
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    parser.add_argument("--link-parser", type=Path, default=DEFAULT_LINK_PARSER)
    args = parser.parse_args()
    if args.max_linkages < 1:
        parser.error("--max-linkages must be positive")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    if not args.link_parser.is_file():
        parser.error("link-parser is missing; run ./scripts/seman2 install-tools")

    fixtures = json.loads((POC_DIR / "fixtures.json").read_text(encoding="utf-8"))
    dictionary = Dictionary("en")
    results = []
    native_records = []
    strict_parameters = {
        "max_null_count": 0,
        "islands_ok": False,
        "spell_guess": False,
        "repeatable_rand": True,
    }
    for fixture in fixtures:
        strict, raw = parse_pass(
            fixture,
            dictionary,
            args.max_linkages,
            args.timeout_seconds,
            max_null_count=0,
            islands_ok=False,
            pass_name="strict",
        )
        add_alternative_relations(strict)
        native_records.extend(raw)
        recovery = None
        if fixture["expected_status"] == "strict_parse_failure":
            recovery, raw = parse_pass(
                fixture,
                dictionary,
                args.max_linkages,
                args.timeout_seconds,
                max_null_count=fixture["recovery_max_null_count"],
                islands_ok=True,
                pass_name="null-link-recovery",
            )
            if recovery["linkages"]:
                recovery["status"] = "partial_parse_with_null_links"
            add_alternative_relations(recovery)
            native_records.extend(raw)
        results.append(
            {
                **fixture,
                "source_observation": {
                    "id": f"source:{fixture['id']}",
                    "text": fixture["sentence"],
                    "charspan": [0, len(fixture["sentence"])],
                },
                "analysis_attribution": {
                    "producer": "Link Grammar",
                    "dictionary_language": "en",
                    "binding": "linkgrammar Python bindings",
                },
                "strict_parameters": strict_parameters,
                "strict_parse": strict,
                "null_link_recovery": recovery,
            }
        )

    validate(results, args.max_linkages)
    strict_linkages = [
        linkage for result in results for linkage in result["strict_parse"]["linkages"]
    ]
    recovery_linkages = [
        linkage
        for result in results
        if result["null_link_recovery"] is not None
        for linkage in result["null_link_recovery"]["linkages"]
    ]
    summary = {
        "verdict": "GO_ATTRIBUTED_LINK_GRAMMAR_ALTERNATIVES_AND_FAILURES",
        "fixture_count": len(results),
        "strict_parse_successes": sum(
            result["strict_parse"]["status"] == "parsed" for result in results
        ),
        "strict_parse_failures": sum(
            result["strict_parse"]["status"] == "strict_parse_failure"
            for result in results
        ),
        "strict_linkage_count": len(strict_linkages),
        "recovery_linkage_count": len(recovery_linkages),
        "fixtures_hitting_linkage_limit": sum(
            result["strict_parse"]["limit_reached_or_sampled"] for result in results
        ),
        "typed_link_count": sum(len(linkage["links"]) for linkage in strict_linkages),
        "strict_linkages_with_constituents": sum(
            linkage["constituency"]["available"] for linkage in strict_linkages
        ),
        "strict_linkages_with_costs": len(strict_linkages),
        "strict_linkages_preserving_source": sum(
            linkage["source_coverage"]["source_text_preserved"]
            for linkage in strict_linkages
        ),
        "ambiguous_fixture_distinct_constituent_trees": len(
            {
                linkage["constituency"]["bracketed"]
                for result in results
                if result["phenomenon"] == "ambiguous"
                for linkage in result["strict_parse"]["linkages"]
            }
        ),
        "by_fixture": {
            result["id"]: {
                "status": result["strict_parse"]["status"],
                "found": result["strict_parse"]["counts"][
                    "found_before_postprocessing"
                ],
                "valid_returned": result["strict_parse"]["counts"][
                    "valid_returned"
                ],
            }
            for result in results
        },
    }

    output_dir = POC_DIR / "output"
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (raw_dir / "native-linkages.json").write_text(
        json.dumps(native_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    version_output = subprocess.run(
        [str(args.link_parser), "--version"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_platform": platform.platform(),
        "python_binding_version": linkgrammar.__version__,
        "dictionary_version": dictionary.linkgrammar_get_dict_version(),
        "dictionary_locale": dictionary.linkgrammar_get_dict_locale(),
        "link_parser_version_output": version_output,
        "parameters": {
            "language": "en",
            "max_linkages": args.max_linkages,
            "timeout_seconds": args.timeout_seconds,
            **strict_parameters,
            "short_length": 16,
            "display_morphology": True,
        },
        "recovery_policy": {
            "only_after_strict_failure": True,
            "islands_ok": True,
            "result_is_labeled_partial": True,
        },
    }
    (output_dir / "versions-and-parameters.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"NLP-05: {summary['strict_parse_successes']} strict successes, "
        f"{summary['strict_parse_failures']} explicit strict failure"
    )
    print(
        f"linkages: {summary['strict_linkage_count']} strict + "
        f"{summary['recovery_linkage_count']} partial recovery; "
        f"typed links: {summary['typed_link_count']}"
    )


if __name__ == "__main__":
    main()
