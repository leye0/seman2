"""Characterize pathological first-pass grammar parses in 5,000 real novel sentences.

Unlike an optimization benchmark, this does not change beam, grammar, timeout,
scoring, or k-best effort limit. It preserves the original sentence order and
the ordinary compiled-structure observations, including WordNet's warmed state.
Timings are recorded separately for lexical lattice, forest recognition,
k-best witness extraction, structure observation, and full first-pass walltime.

Output: per-sentence JSONL + aggregate JSON with tail cohorts, token-length
strata, lexical/forest complexity, phase attribution and reproducible examples.
Claims are descriptive associations, not causal or proof of grammar correctness.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from research.verbnet_lr.compiled_structure_snap import CompiledStructureReplayer
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA="51650d348820a64ca4d4233da035f804819d2231801b59373db4e1279a1985e0"


def quantile(values, portion):
    if not values:
        return None
    ordered=sorted(values)
    point=(len(ordered)-1)*portion
    lo=int(point)
    hi=min(lo+1,len(ordered)-1)
    return ordered[lo]*(hi-point)+ordered[hi]*(point-lo)


def distribution(values):
    values=list(values)
    if not values:
        return {"n":0}
    return {
        "n":len(values),"p50":round(quantile(values,.5),4),
        "p90":round(quantile(values,.9),4),
        "p95":round(quantile(values,.95),4),
        "p99":round(quantile(values,.99),4),
        "max":round(max(values),4),
        "mean":round(sum(values)/len(values),4),
        "total":round(sum(values),4),
    }


def token_band(n):
    if n<=8:return "04-08"
    if n<=16:return "09-16"
    if n<=24:return "17-24"
    return "25-32"


def characterization(text,lattice):
    tokens=tuple(lattice.tokens)
    candidates=lattice.candidates
    spans=defaultdict(list)
    exact=defaultdict(list)
    for c in candidates:
        spans[(c.span_start,c.span_end)].append(c)
    for token in tokens:
        exact[token.index]=spans.get((token.start,token.end),())
    token_categories=[set(c.category for c in exact[t.index]) for t in tokens]
    ambiguous=sum(len(cats)>=2 for cats in token_categories)
    strongly_ambiguous=sum(len(cats)>=4 for cats in token_categories)
    per_token_counts=[len(exact[t.index]) for t in tokens]
    lexical_pos=Counter(c.category for c in candidates)
    single_token_spans={(t.start,t.end) for t in tokens}
    n=len(tokens)
    return {
        "tokens":n,
        "length_band":token_band(n),
        "characters":len(text),
        "lexical_candidates":len(candidates),
        "lexical_spans":len(spans),
        "candidates_per_token":round(len(candidates)/max(1,n),3),
        "max_readings_one_token":max(per_token_counts,default=0),
        "mean_readings_one_token":round(sum(per_token_counts)/max(1,n),3),
        "ambiguous_positions":ambiguous,
        "highly_ambiguous_positions":strongly_ambiguous,
        "distinct_lexical_categories":len(lexical_pos),
        "cross_token_or_split_spans":sum(key not in single_token_spans
                                        for key in spans),
        "question_or_exclamation":int("?" in text or "!" in text),
        "comma_count":text.count(","),
        "semicolon_or_colon":int(";" in text or ":" in text),
        "quoted":int('"' in text or "'" in text),
        "dash_or_hyphen":int("-" in text),
        "has_prep_reading":int("PREP" in lexical_pos),
        "has_pronoun_reading":int("PRONOUN" in lexical_pos),
        "has_conjunction_reading":int(bool({"CONJ","COORD"} & set(lexical_pos))),
        "has_relative_reading":int(any("REL" in c for c in lexical_pos)),
        "has_verb_reading":int("V" in lexical_pos),
    }


def measured_sentence(index,row,resources,native,memory,kbest_work_limit):
    text=row["text"]
    start=perf_counter_ns()
    lex_start=perf_counter_ns()
    lattice=build_lattice(text,resources.lexicon,multiword_max=1)
    lex_ms=(perf_counter_ns()-lex_start)/1e6
    metadata=characterization(text,lattice)
    parse_start=perf_counter_ns()
    result=native._vector_grammar.parse_lattice(
        lattice,beam=native.beam,max_items=20000,
        goal_category=native.goal_category,
        kbest_work_limit=kbest_work_limit)
    parse_wall_ms=(perf_counter_ns()-parse_start)/1e6
    best=result.best() if result.completed else None
    indexed=False
    index_error=None
    index_ms=0.0
    if best is not None:
        obs_start=perf_counter_ns()
        try:
            memory.observe(best,lattice=lattice)
            indexed=True
        except (ValueError,OverflowError) as exc:
            index_error=str(exc)
        index_ms=(perf_counter_ns()-obs_start)/1e6
    full_ms=(perf_counter_ns()-start)/1e6
    stats=result.stats
    recognition_ms=float(stats.get("recognition_ms",0.0))
    best_ms=float(stats.get("best_ms",0.0))
    record={
        "index":index,"book_ordinal":row["ordinal"],
        "sentence_sha256":sha256(text.encode()).hexdigest(),
        "preview":text[:145],
        **metadata,
        "completed":best is not None,
        "indexed":indexed,"index_error":index_error,
        "kbest_budget_exceeded":bool(stats.get("kbest_budget_exceeded")),
        "forest_budget_exceeded":bool(stats.get("budget_exceeded")),
        "lexing_ms":round(lex_ms,5),
        "recognition_ms":round(recognition_ms,5),
        "kbest_ms":round(best_ms,5),
        "parse_wall_ms":round(parse_wall_ms,5),
        "index_ms":round(index_ms,5),
        "full_ms":round(full_ms,5),
        "forest_nodes":stats.get("forest_nodes",0),
        "structural_derivations":stats.get("structural_derivations",0),
        "partial_states":stats.get("partial_states",0),
        "partial_derivations":stats.get("partial_derivations",0),
        "partial_proposals":stats.get("partial_proposals",0),
        "recognition_operations":stats.get("recognition_operations",0),
        "kbest_work_units":stats.get("kbest_work_units",0),
        "unification_attempts":stats.get("unification_attempts",0),
        "unification_rejections":stats.get("unification_rejections",0),
        "combinations_visited_for_best":stats.get("combinations_visited_for_best",0),
        "compact_analyses":stats.get("compact_analyses",0),
        "context_cache_hits":stats.get("constraint_context_cache_hits",0),
        "unification_cache_hits":stats.get("unification_cache_hits",0),
        "phase_dominant":max((
            ("lexing",lex_ms),("forest",recognition_ms),("kbest",best_ms)
        ),key=lambda p:p[1])[0],
    }
    return record


NUMERIC_FACTORS=(
    "tokens","characters","lexical_candidates","lexical_spans",
    "candidates_per_token","max_readings_one_token",
    "mean_readings_one_token","ambiguous_positions",
    "highly_ambiguous_positions","cross_token_or_split_spans",
    "forest_nodes","structural_derivations","partial_states",
    "partial_derivations","recognition_operations",
    "kbest_work_units","combinations_visited_for_best",
    "unification_attempts","unification_rejections",
)
BOOLEAN_FACTORS=(
    "question_or_exclamation","semicolon_or_colon","quoted",
    "dash_or_hyphen","has_prep_reading","has_pronoun_reading",
    "has_conjunction_reading","has_relative_reading","has_verb_reading",
    "kbest_budget_exceeded","forest_budget_exceeded",
)


def characterize_tail(records, baseline=None):
    assert records
    ms=[r["full_ms"] for r in records]
    med=quantile(ms,.5)
    p95=quantile(ms,.95)
    p99=quantile(ms,.99)
    cutoffs={
        "over_5x_median":5*med,
        "over_10x_median":10*med,
        "over_1000ms":1000.0,
        "top_5pct_p95":p95,
        "top_1pct_p99":p99,
    }
    def cohort_statistics(rows):
        if not rows:
            return {"count":0}
        out={"count":len(rows),"share_pct":round(100*len(rows)/len(records),3)}
        for attr in ("full_ms","lexing_ms","recognition_ms","kbest_ms",
                     "tokens","lexical_candidates","ambiguous_positions",
                     "partial_states","structural_derivations",
                     "kbest_work_units"):
            out[attr]=distribution(r[attr] for r in rows)
        out["dominant_phase"]=dict(Counter(r["phase_dominant"] for r in rows))
        out["completed_pct"]=round(100*sum(r["completed"] for r in rows)/len(rows),3)
        out["kbest_budget_exceeded"]=sum(r["kbest_budget_exceeded"] for r in rows)
        return out
    cohorts={
        name:cohort_statistics([r for r in records if r["full_ms"]>=value])
        for name,value in cutoffs.items()
    }
    fast=[r for r in records if r["full_ms"]<=med]
    slow=[r for r in records if r["full_ms"]>=p95]
    comparisons={}
    for key in NUMERIC_FACTORS:
        a=quantile([r[key] for r in fast],.5)
        b=quantile([r[key] for r in slow],.5)
        comparisons[key]={
            "fast_half_p50":round(a,4),"slowest_5pct_p50":round(b,4),
            "median_ratio":round(b/a,3) if a else None
        }
    features={}
    for feature in BOOLEAN_FACTORS:
        positive=[r for r in records if r[feature]]
        negative=[r for r in records if not r[feature]]
        positives_slow=sum(r["full_ms"]>=p95 for r in positive)
        negatives_slow=sum(r["full_ms"]>=p95 for r in negative)
        pos_rate=positives_slow/len(positive) if positive else None
        neg_rate=negatives_slow/len(negative) if negative else None
        features[feature]={
            "n_present":len(positive),
            "p95_slow_rate_if_present_pct":round(100*pos_rate,3) if pos_rate is not None else None,
            "p95_slow_rate_if_absent_pct":round(100*neg_rate,3) if neg_rate is not None else None,
            "unadjusted_risk_ratio":round(pos_rate/neg_rate,3) if neg_rate else None,
        }
    by_length={}
    for band in ("04-08","09-16","17-24","25-32"):
        rows=[r for r in records if r["length_band"]==band]
        if not rows:continue
        by_length[band]={
            **cohort_statistics(rows),
            "full_ms":distribution(r["full_ms"] for r in rows),
            "lexical_candidates":distribution(r["lexical_candidates"] for r in rows),
            "ambiguous_positions":distribution(r["ambiguous_positions"] for r in rows),
            "over_5x_global_median":sum(r["full_ms"]>=5*med for r in rows),
            "top_5pct_global":sum(r["full_ms"]>=p95 for r in rows),
        }
    def preview(r):
        return {k:r[k] for k in (
            "index","book_ordinal","sentence_sha256","preview","tokens",
            "lexical_candidates","ambiguous_positions",
            "cross_token_or_split_spans","completed","kbest_budget_exceeded",
            "forest_budget_exceeded","phase_dominant","lexing_ms",
            "recognition_ms","kbest_ms","full_ms","forest_nodes",
            "structural_derivations","partial_states","partial_derivations",
            "combinations_visited_for_best","kbest_work_units"
        )}
    worst=sorted(records,key=lambda r:r["full_ms"],reverse=True)[:40]
    notable_by_phase={
        phase:[preview(r) for r in sorted(
            (r for r in records if r["phase_dominant"]==phase),
            key=lambda r:r["full_ms"],reverse=True)[:10]]
        for phase in ("lexing","forest","kbest")
    }
    total=sum(ms)
    tail=sorted(ms,reverse=True)
    return {
        "n":len(records),
        "full_ms":distribution(ms),
        "lexing_ms":distribution(r["lexing_ms"] for r in records),
        "recognition_ms":distribution(r["recognition_ms"] for r in records),
        "kbest_ms":distribution(r["kbest_ms"] for r in records),
        "kbest_work_units":distribution(r["kbest_work_units"] for r in records),
        "combinations_visited_for_best":distribution(r["combinations_visited_for_best"] for r in records),
        "outlier_threshold_ms":{k:round(v,4) for k,v in cutoffs.items()},
        "outlier_cohorts":cohorts,
        "runtime_concentration":{
            "top_1pct_share_pct":round(100*sum(tail[:math.ceil(.01*len(tail))])/total,3),
            "top_5pct_share_pct":round(100*sum(tail[:math.ceil(.05*len(tail))])/total,3),
            "top_10pct_share_pct":round(100*sum(tail[:math.ceil(.10*len(tail))])/total,3),
        },
        "by_token_length":by_length,
        "fast_half_vs_slowest_5pct":comparisons,
        "descriptive_flags_unadjusted":features,
        "completion":{
            "complete":sum(r["completed"] for r in records),
            "indexable":sum(r["indexed"] for r in records),
            "no_full_analysis":sum(not r["completed"] for r in records),
            "kbest_work_limit_reached":sum(r["kbest_budget_exceeded"] for r in records),
            "forest_node_budget_reached":sum(r["forest_budget_exceeded"] for r in records),
        },
        "top_40_slowest":list(map(preview,worst)),
        "slowest_by_dominant_phase":notable_by_phase,
        "notes":[
            "No timeouts are imposed. k-best work budget is identical to the last 5000-sentence benchmark.",
            "Recognition_ms, kbest_ms and lexing_ms describe phases, but are not additive to full walltime due to bookkeeping and observation.",
            "The entire 5000-sentence training prefix is replayed in original sequence, with WordNet mutable state retained.",
            "The corpus's original text is not uploaded; only short previews from outliers and SHA256s are in the report.",
            "POS observations are lexical *possibilities*, not validated parse categories.",
            "Flag risk ratios are unadjusted, observational, and confounded by sentence length and candidate count.",
            "Outlier ranking on total time differs from outlier ranking on grammar-only time; both phase and total are displayed.",
        ]
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--size",type=int,default=5000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--checkpoint",type=int,default=25)
    ap.add_argument("--kbest-work-limit",type=int,default=100000)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()
    book=TRAIN_BOOKS[0]
    core,info=download(book)
    if info["sha256"]!=SOURCE_SHA:
        raise RuntimeError("Gutenberg novel content changed; cannot compare run")
    rows,corpus_stats=extract(book,core,length_min=4,length_max=args.max_tokens)
    if len(rows)<args.size:
        raise ValueError("Insufficient eligible sentences")
    rows=rows[:args.size]
    args.out_dir.mkdir(parents=True,exist_ok=True)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=args.wordnet_dir)
    native=Parser(resources,cache_size=0,max_items=20000)
    memory=CompiledStructureReplayer(resources)
    print("PROFILE_CORPUS",json.dumps({
        "novel":book.title,"ebook_id":book.ebook_id,
        "count":len(rows),"sha256":info["sha256"],
        "kbest_work_limit":args.kbest_work_limit,
        "extraction":corpus_stats,
    }),flush=True)
    observations=[]
    path=args.out_dir/"per_sentence.jsonl"
    with path.open("w",encoding="utf8",buffering=1) as outfile:
        for i,row in enumerate(rows):
            obs=measured_sentence(
                i,row,resources,native,memory,args.kbest_work_limit)
            observations.append(obs)
            # Preserve granular progress even if runner is interrupted.
            outfile.write(json.dumps(obs,separators=(",",":"))+"\n")
            if (i+1)%args.checkpoint==0 or i==len(rows)-1:
                chunk=observations[-args.checkpoint:]
                print("PROFILE_PROGRESS",json.dumps({
                    "seen":i+1,
                    "completed":sum(r["completed"] for r in observations),
                    "kbest_limit_exceeded":sum(r["kbest_budget_exceeded"] for r in observations),
                    "last_window_p50_ms":round(quantile([r["full_ms"] for r in chunk],.5),3),
                    "last_window_max_ms":round(max(r["full_ms"] for r in chunk),3),
                    "slowest_index_so_far":max(observations,key=lambda r:r["full_ms"])["index"],
                }),flush=True)
    report={
        "schema":"Seman2-5000-Gutenberg-first-pass-pathology-v1",
        "source":{"book":book.title,"ebook_id":book.ebook_id,
                  "sha256":info["sha256"],"sentences":len(rows),
                  "max_tokens":args.max_tokens},
        "parser":{"forest_max_items":20000,"kbest_work_limit":args.kbest_work_limit},
        "results":characterize_tail(observations)
    }
    (args.out_dir/"summary.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    result=report["results"]
    print("PROFILE_SUMMARY",json.dumps({
        "n":result["n"],"full_ms":result["full_ms"],
        "runtime_concentration":result["runtime_concentration"],
        "completion":result["completion"],
        "outlier_threshold_ms":result["outlier_threshold_ms"],
        "outlier_counts":{k:v["count"] for k,v in result["outlier_cohorts"].items()},
        "dominant_phase_top5pct":result["outlier_cohorts"]["top_5pct_p95"]["dominant_phase"],
        "top_10_slowest":result["top_40_slowest"][:10]
    }),flush=True)


if __name__=="__main__":
    main()
