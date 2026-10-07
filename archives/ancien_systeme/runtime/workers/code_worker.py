#!/usr/bin/env python3
"""Losslessly parse a code observation with the routed Tree-sitter grammar."""

from __future__ import annotations

import json
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

from tree_sitter_language_pack import get_parser


source = request["text"].encode("utf-8")
language = request["language"]
parser = get_parser(language)
tree = parser.parse(source)


def encode(node, parent=None, child_index=None):
    field_name = (
        parent.field_name_for_child(child_index)
        if parent is not None and child_index is not None
        else None
    )
    return {
        "type": node.type,
        "named": node.is_named,
        "missing": node.is_missing,
        "error": node.type == "ERROR",
        "field_name": field_name,
        "byte_span": [node.start_byte, node.end_byte],
        "point_span": [list(node.start_point), list(node.end_point)],
        "text": source[node.start_byte : node.end_byte].decode("utf-8"),
        "children": [
            encode(child, node, index) for index, child in enumerate(node.children)
        ],
    }


root = encode(tree.root_node)
json.dump(
    {
        "status": "parsed",
        "language": language,
        "root_type": tree.root_node.type,
        "has_error": tree.root_node.has_error,
        "source_reconstructed": root["text"] == request["text"],
        "cst": root,
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
