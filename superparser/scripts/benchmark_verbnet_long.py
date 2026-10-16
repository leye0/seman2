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
from seman_parser.segmentation import tokenize

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
        "token_only_guard6": SemanCompiledReader(resources, stack_checkpoints=True,
                                checkpoint_budget=6, construction_guard=True,
                                token_only_lattice=True),
    }
    for case in cases:
        for model in modes.values():
            model.parse(case["text"])
    records = {mode: [] for mode in modes}
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
