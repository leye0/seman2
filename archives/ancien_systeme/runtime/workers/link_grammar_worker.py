#!/usr/bin/env python3
from __future__ import annotations

import json
import resource
import sys


request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
from linkgrammar import Clinkgrammar as clg
from linkgrammar import Dictionary, ParseOptions, Sentence

options = ParseOptions(
    verbosity=0,
    linkage_limit=int(request["max_linkages"]),
    min_null_count=0,
    max_null_count=0,
    islands_ok=False,
    spell_guess=False,
    repeatable_rand=True,
    max_parse_time=int(request["parse_timeout_seconds"]),
)
sentence = Sentence(request["text"], Dictionary("en"), options)
split_status = sentence.split()
linkages = []
if split_status >= 0:
    for linkage in sentence.parse():
        tokens = [
            {
                "index": index,
                "form": linkage.word(index),
                "charspan": [
                    linkage.word_char_start(index),
                    linkage.word_char_end(index),
                ],
            }
            for index in range(linkage.num_of_words())
        ]
        links = []
        for index, link in enumerate(linkage.links()):
            links.append(
                {
                    "type": clg.linkage_get_link_label(linkage._obj, index),
                    "left_word": clg.linkage_get_link_lword(linkage._obj, index),
                    "right_word": clg.linkage_get_link_rword(linkage._obj, index),
                    "left_connector": link.left_label,
                    "right_connector": link.right_label,
                }
            )
        linkages.append(
            {
                "tokens": tokens,
                "links": links,
                "costs": {
                    "unused_word": linkage.unused_word_cost(),
                    "disjunct": linkage.disjunct_cost(),
                    "link": linkage.link_cost(),
                },
                "violation": linkage.violation_name(),
                "constituent_tree": linkage.constituent_tree(2),
            }
        )
json.dump(
    {
        "status": "parsed" if linkages else "failure",
        "split_status": split_status,
        "linkage_count": len(linkages),
        "linkages": linkages,
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
