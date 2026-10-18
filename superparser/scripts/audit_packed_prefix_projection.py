"""Single-pass read-only audit of a physically interned prefix edge model.

No grammar/runtime changes. Canonical packed forest remains authoritative.
Every original PartialDerivation must round-trip through the compressed
representation, *including ordered edges from different rule variants*.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from research.verbnet_lr.packed_prefix_projection import build_projection, FlatPrefixProjection, pack_flat_direct
from scripts.benchmark_heavy_sentence_ab import BANDS,choose_cases
from seman_parser.engine import Parser,ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


def group(rows):
    count=len(rows)
    keys=("partials","shared_groups","original_edges","interned_edges",
          "reused_edge_occurrences","original_edge_objects_estimated_bytes",
          "projected_edge_objects_estimated_bytes","flat_arrays_bytes")
    agg={k:sum(r[k] for r in rows) for k in keys}
    agg["n"]=count
    agg["edge_reuse_rate"]=(round(1-agg["interned_edges"]/agg["original_edges"],5)
                             if agg["original_edges"] else 0)
    agg["byte_ratio"]=(round(agg["projected_edge_objects_estimated_bytes"]/
                             agg["original_edge_objects_estimated_bytes"],5)
                       if agg["original_edge_objects_estimated_bytes"] else 0)
    agg["flat_byte_ratio"]=(round(agg["flat_arrays_bytes"]/
                                 agg["original_edge_objects_estimated_bytes"],5)
                        if agg["original_edge_objects_estimated_bytes"] else 0)
    agg["p50_projection_ms"]=round(median(r["projection_ms"] for r in rows),4) if rows else None
    agg["projection_total_ms"]=round(sum(r["projection_ms"] for r in rows),3)
    agg["flat_conversion_total_ms"]=round(sum(r["flat_conversion_ms"] for r in rows),3)
    agg["direct_conversion_total_ms"]=round(sum(r["direct_conversion_ms"] for r in rows),3)
    agg["parser_total_ms"]=round(sum(r["parse_ms"] for r in rows),3)
    agg["saturation_count"]=sum(r["budget_exceeded"] for r in rows)
    return agg


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--per-book-per-band",type=int,default=4)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    cases,source=choose_cases(args.per_book_per_band)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    parser=Parser(resources,cache_size=0,max_items=20000)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    records=[]
    with (args.out_dir/"per_sentence.jsonl").open("w",encoding="utf8",buffering=1) as output:
        for i,item in enumerate(cases):
            lattice=build_lattice(item["text"],resources.lexicon,multiword_max=1)
            begun=perf_counter_ns()
            parsed=parser.parse_grammar_lattice(
                lattice,max_items=20000,kbest_work_limit=100000)
            best=parsed.best() if parsed.completed else None
            parse_ms=(perf_counter_ns()-begun)/1e6
            if parsed.shared_forest is None:
                raise AssertionError("A canonical forest is required for the audit")
            start=perf_counter_ns()
            projection=build_projection(parsed.shared_forest,validate=True)
            projection_ms=(perf_counter_ns()-start)/1e6
            metrics=projection.metrics(parsed.shared_forest)
            flat_start=perf_counter_ns()
            flat=FlatPrefixProjection(projection)
            flat_checked=flat.verify(parsed.shared_forest)
            flat_ms=(perf_counter_ns()-flat_start)/1e6
            flat_metrics=flat.metrics(parsed.shared_forest)
            direct_start=perf_counter_ns()
            direct=pack_flat_direct(parsed.shared_forest,validate=True)
            direct_ms=(perf_counter_ns()-direct_start)/1e6
            if direct.group_of!=flat.group_of or direct.variant_edges!=flat.variant_edges or direct.children!=flat.children or direct.prev_groups!=flat.prev_groups or direct.member_offsets!=flat.member_offsets or direct.member_rules!=flat.member_rules or direct.member_ids!=flat.member_ids:
                raise AssertionError("Direct and indirect packing disagree")
            if direct.metrics(parsed.shared_forest)!=flat_metrics:
                raise AssertionError("Direct packing changed stored byte footprint")
            if flat_checked!=metrics["original_edges"]:
                raise AssertionError("Flat packed prefix projection lost edges")
            row={
                "index":i,"book_id":item["book_id"],"ordinal":item["ordinal"],
                "band":item["band"],"tokens":item["tokens"],
                "sentence_sha256":sha256(item["text"].encode()).hexdigest(),
                "text":item["text"],"completed":best is not None,
                "budget_exceeded":bool(parsed.stats.get("budget_exceeded")),
                "parse_ms":round(parse_ms,4),"projection_ms":round(projection_ms,4),
                "flat_conversion_ms":round(flat_ms,4),
                "direct_conversion_ms":round(direct_ms,4),
                "flat_arrays_bytes":flat_metrics["flat_arrays_bytes"],
                "validated_flat_edges":flat_checked,
                **metrics,
            }
            records.append(row)
            output.write(json.dumps(row,ensure_ascii=False)+"\n")
            if (i+1)%8==0:
                print("PACKED_PREFIX_PROGRESS",json.dumps({
                    "seen":i+1,"total_partials":sum(r["partials"] for r in records),
                    "original_edges":sum(r["original_edges"] for r in records),
                    "interned_edges":sum(r["interned_edges"] for r in records)
                }),flush=True)
    result={
        "schema":"packed-prefix-reversible-projection-v1",
        "source":source,
        "all":group(records),
        "by_band":{b:group([r for r in records if r["band"]==b]) for b,_,_ in BANDS},
        "notes":[
            "All canonical PackedPartial derivations were reconstructed exactly in original order.",
            "Variant indices and rule-specific previous partial IDs remain independently recoverable.",
            "This builds a SECOND projection after parsing; it does NOT reduce the memory of the active parser.",
            "Python object-based prefix groups increase storage despite deduplicating recognition edges.",
            "Flat packed arrays include per-rule membership and ordered edge references but exclude live hash indexes.",
            "Flat storage is post-build and read-only, NOT an online memory benchmark or production optimizer.",
            "Direct packer uses temporary dictionaries, but no intermediary PrefixGroup objects; indexes are discarded on completion.",
            "Direct and indirect flat array contents are compared byte-for-byte using Python array equality.",
            "Compression ratios are specific to this encoding, not promised future parser speedups.",
            "The full grammar tree and lexical lattice remain untouched; no rules or corpus text changed.",
            "All sources are pinned novels; no author-held-out validation in this pilot.",
        ],
    }
    (args.out_dir/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("PACKED_PREFIX_FINAL",json.dumps(result),flush=True)


if __name__=="__main__":
    main()
