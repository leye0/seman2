"""Long sentence stress benchmark for Seman2 L→R experimental readers.

Separate from grammar-quality gold cases: this measures wall time, token
progress and completion. A fast early STOP is NOT a successful long parse.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.segmentation import tokenize, build_lattice

ROOT = Path(__file__).resolve().parents[1]


def quant(values, fraction):
    values = sorted(values)
    if not values:
        return None
    return round(values[min(len(values)-1,int((len(values)-1)*fraction))], 4)


def run(wordnet_dir=None, corpus=None, repetitions=3):
    path = Path(corpus or ROOT / "research" / "verbnet_lr" / "long_sentence_stress.jsonl")
    cases = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    resources = ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet_dir)
    modes = {
        "baseline": SemanCompiledReader(resources),
        "local3": SemanCompiledReader(resources, stack_checkpoints=True, checkpoint_budget=3),
        "local3_guard": SemanCompiledReader(resources, stack_checkpoints=True,
                                           checkpoint_budget=3, construction_guard=True),
        "fast_baseline": SemanCompiledReader(resources, fast_multiword=True),
        "fast_local3_guard": SemanCompiledReader(resources, stack_checkpoints=True,
                                   checkpoint_budget=3, construction_guard=True,
                                   fast_multiword=True),
        "early_local3_guard": SemanCompiledReader(resources, stack_checkpoints=True,
                                   checkpoint_budget=3, construction_guard=True,
                                   early_construction_guard=True),
        "token_only_baseline": SemanCompiledReader(resources, token_only_lattice=True),
        "token_only_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                               checkpoint_budget=3, construction_guard=True,
                               token_only_lattice=True),
        "token_cache_baseline": SemanCompiledReader(resources, token_only_lattice=True,
                                                    fast_multiword=True),
        "token_cache_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True, fast_multiword=True),
        "promoted_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True,
                                infer_unary_promotions=True),
        "reduce_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True, infer_unary_promotions=True,
                                reduce_checkpoints=True),
        "parent_follow_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True, infer_unary_promotions=True,
                                reduce_checkpoints=True, parent_follow_reduce=True),
        "follow_only_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True, infer_unary_promotions=True,
                                reduce_checkpoints=True, reduce_follow_only=True),
        "reachable_guard3": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=3, construction_guard=True,
                                token_only_lattice=True, infer_unary_promotions=True,
                                reduce_checkpoints=True, reachable_checkpoints_only=True),
        "prefix_guard3": SemanCompiledReader(
            resources, stack_checkpoints=True, checkpoint_budget=3,
            construction_guard=True, token_only_lattice=True,
            infer_unary_promotions=True, reduce_checkpoints=True,
            reachable_checkpoints_only=True, terminal_prefix_preference=True),
        "prefix_follow3": SemanCompiledReader(
            resources, stack_checkpoints=True, checkpoint_budget=3,
            construction_guard=True, token_only_lattice=True,
            infer_unary_promotions=True, reduce_checkpoints=True,
            reduce_follow_only=True, reachable_checkpoints_only=True,
            terminal_prefix_preference=True),
        "extension_prefix3": SemanCompiledReader(
            resources, stack_checkpoints=True, checkpoint_budget=3,
            construction_guard=True, token_only_lattice=True,
            infer_unary_promotions=True, reduce_checkpoints=True,
            reachable_checkpoints_only=True, terminal_prefix_preference=True,
            extension_checkpoints=True),
        "extension_follow3": SemanCompiledReader(
            resources, stack_checkpoints=True, checkpoint_budget=3,
            construction_guard=True, token_only_lattice=True,
            infer_unary_promotions=True, reduce_checkpoints=True,
            reduce_follow_only=True, reachable_checkpoints_only=True,
            terminal_prefix_preference=True, extension_checkpoints=True),
        "token_only_guard6": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=6, construction_guard=True,
                                token_only_lattice=True),
    }
    for case in cases:
        for model in modes.values():
            model.parse(case["text"])
    records = {mode: [] for mode in modes}
    diagnostics = {}
    # Diagnostics are constructed outside the measured wall-time window.
    # They never alter the parsing choices; they expose first-reader
    # failures and actual candidate POS around the stopping token.
    selected_modes = {"baseline", "reachable_guard3", "follow_only_guard3", "prefix_guard3", "extension_prefix3", "extension_follow3"}
    for rep in range(repetitions):
        for case in cases:
            token_count = len(tokenize(case["text"]))
            for mode, model in modes.items():
                started = perf_counter()
                result = model.parse(case["text"])
                elapsed = (perf_counter() - started)*1000
                # STOP/ACCEPT events refer to actual current input position.
                # Report furthest observed position *and* final progress.
                events = result.outcome.events
                terminal = next((x for x in reversed(events)
                                 if x.action in {"STOP","ACCEPT"}),None)
                final_at = terminal.at if terminal else 0
                furthest = max((ev.at for ev in events),default=0)
                if rep == 0 and mode in selected_modes and not result.complete:
                    toks = tokenize(case["text"])
                    site = min(max(0, final_at), len(toks)-1)
                    lo, hi = max(0, site-4), min(len(toks), site+5)
                    lexical = build_lattice(
                        case["text"], resources.lexicon, multiword_max=1)
                    pos_categories = {}
                    for cand in lexical.candidates:
                        pos_categories.setdefault(
                            (cand.span_start, cand.span_end), set()
                        ).add(cand.category)
                    diagnostics.setdefault(mode, []).append({
                        "id": case["id"],
                        "stop_at": final_at,
                        "reason": result.outcome.reason,
                        "window": [
                            {"at": i, "word": toks[i].text,
                             "categories": sorted(pos_categories.get(
                                 (toks[i].start,toks[i].end), ()))}
                            for i in range(lo, hi)
                        ],
                        "last_events": [
                            {"at": e.at, "action": e.action,
                             "symbol": e.expected, "detail": e.detail}
                            for e in events[-18:]
                        ]
                    })
                records[mode].append({
                    "id":case["id"], "words":case["length_words"],
                    "tokens":token_count, "complete":bool(result.complete),
                    "total_ms":round(elapsed,4),
                    "lexical_ms":round(result.lexical_ms,4),
                    "reading_ms":round(result.reading_ms,4),
                    "final_token_fraction":round(min(1,final_at/max(1,token_count)),3),
                    "furthest_fraction":round(min(1,furthest/max(1,token_count)),3),
                    "reason":result.outcome.reason if not result.complete else "",
                    "restores":result.outcome.counters.get("checkpoint_restores_total",0),
                    "max_stack_depth":result.outcome.counters.get("max_stack_depth",0),
                })
    # Collect active-stack witnesses only after ALL timed repetitions.
    # A diagnostic retry must not influence measured wall times or count as
    # an additional repetition; this is a separate non-timed experiment.
    for case in cases:
        for mode in sorted(selected_modes - {"baseline"}):
            probe = modes[mode].parse(case["text"], diagnose=True)
            target = next(
                (row for row in diagnostics.get(mode, ()) if row["id"] == case["id"]),
                None,
            )
            if target is not None:
                target["stack_failures"] = list(probe.failure_sites)
                target["diagnostic_parse_agreed"] = (
                    bool(probe.complete) ==
                    next(row["complete"] for row in records[mode]
                         if row["id"] == case["id"])
                )
    return {
        "schema":1,
        "source":"manually composed English stress sentences, WITHOUT annotated gold syntax",
        "repetitions":repetitions,
        "cases":len(cases),
        "results":{
            mode:{
                "mean_words":round(sum(x["words"] for x in vals)/len(vals),2),
                "complete_sentences":sum(x["complete"] for x in vals)/repetitions,
                "p50_ms":quant([x["total_ms"] for x in vals],0.5),
                "lexical_p50_ms":quant([x["lexical_ms"] for x in vals],0.5),
                "reading_p50_ms":quant([x["reading_ms"] for x in vals],0.5),
                "p95_ms":quant([x["total_ms"] for x in vals],0.95),
                "p99_ms":quant([x["total_ms"] for x in vals],0.99),
                "max_ms":max(x["total_ms"] for x in vals),
                "total_restores":sum(x["restores"] for x in vals),
                "max_restores":max(x["restores"] for x in vals),
                "p50_restores":quant([x["restores"] for x in vals],0.5),
                "cases_reaching_75pct_of_tokens":sum(
                    x["final_token_fraction"]>=0.75 for x in vals)/repetitions,
                "by_length":[
                    {"id":case["id"],"words":case["length_words"],
                     "p50_ms":quant([x["total_ms"] for x in vals if x["id"]==case["id"]],0.5),
                     "lexical_p50_ms":quant([x["lexical_ms"] for x in vals if x["id"]==case["id"]],0.5),
                     "reading_p50_ms":quant([x["reading_ms"] for x in vals if x["id"]==case["id"]],0.5),
                     "complete":next(x["complete"] for x in vals if x["id"]==case["id"]),
                     "first_reason":next(x["reason"] for x in vals if x["id"]==case["id"]),
                     "max_restores":max(x["restores"] for x in vals
                                        if x["id"]==case["id"]),
                     "failure_mode":(
                         "early_stop" if max(x["final_token_fraction"] for x in vals
                                              if x["id"]==case["id"]) < 0.75
                         else "late_stop_or_complete"
                     ),
                     "furthest_token_fraction":max(x["furthest_fraction"] for x in vals
                                                   if x["id"]==case["id"]),
                     "final_token_fraction":max(x["final_token_fraction"] for x in vals
                                                if x["id"]==case["id"])}
                    for case in cases
                ],
            }
            for mode,vals in records.items()
        },
        "diagnostics": diagnostics,
        "warning":[
            "A fast early STOP does not demonstrate efficient long-sentence recognition.",
            "This corpus has no gold trees; completion cannot be scored as syntactic correctness.",
            "No parser grammar or candidate priority is tuned from this stress sample.",
        ],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wordnet-dir")
    p.add_argument("--cases")
    p.add_argument("--repetitions",type=int,default=3)
    p.add_argument("--report",default=str(ROOT/"research"/"verbnet_lr"/"long_stress_report.json"))
    a=p.parse_args()
    if a.repetitions < 1: p.error("repetitions must be >=1")
    report=run(a.wordnet_dir,a.cases,a.repetitions)
    Path(a.report).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({name:{k:v for k,v in row.items() if k != "by_length"}
                      for name,row in report["results"].items()},indent=2))


if __name__=="__main__":
    main()
