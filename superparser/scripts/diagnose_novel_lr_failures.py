"""Explain L-R failure reasons on reproducibly selected Gutenberg prose.

Research-only. Outputs aggregate counts, never raw novel text.
The reader parses every selected sentence WITHOUT learning or snapping,
in order to expose which parser stage halts each full-sentence read.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path

from research.verbnet_lr.gutenberg_novels import (
    TRAIN_BOOKS,download,extract,spread_training,length_band
)
from seman_parser.engine import ParserResources
from seman_parser.segmentation import build_lattice
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
ROOT=Path(__file__).resolve().parents[1]


def failure_family(reason):
    if not reason: return "unknown"
    for prefix in (
        "unconsumed_","unification_failed_","expected_continuation_",
        "no_live_rule_","nonconsuming_recursive_","lexical_features_incompatible_",
        "expected_","grammar_has_no_entry_","construction_guard_"):
        if reason.startswith(prefix):
            return prefix[:-1]
    return reason if len(reason)<50 else reason[:50]


def run(wordnet_dir,limit=3000):
    if limit<=0: raise ValueError("Positive corpus size required")
    works={}
    catalog=[]
    for book in TRAIN_BOOKS:
        core,meta=download(book)
        cases,extraction=extract(book,core,length_min=4,length_max=45)
        works[book.ebook_id]=cases
        catalog.append({"id":book.ebook_id,"sha256":meta["sha256"],
                        "eligible":extraction["eligible"]})
    observations=spread_training(works,limit)
    if len(observations)!=limit:
        raise RuntimeError("Insufficient novel observations")
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    reader=SemanCompiledReader(resources,token_only_lattice=True)
    overall=Counter()
    failure=Counter()
    endings=Counter()
    missing=Counter()
    bands=defaultdict(Counter)
    detail_by_band=defaultdict(Counter)
    missing_per_band=defaultdict(Counter)
    for i,case in enumerate(observations,1):
        text=case["text"]
        lat=build_lattice(text,resources.lexicon,multiword_max=1)
        spans={(c.span_start,c.span_end) for c in lat.candidates}
        tokens=list(lat.tokens)
        content=tokens[:-1] if tokens and tokens[-1].text in (".","!","?") else tokens
        uncovered=[t for t in content if (t.start,t.end) not in spans]
        band=length_band(case["tokens"])
        b=bands[band]
        overall["seen"]+=1;b["seen"]+=1
        if uncovered:
            overall["missing_any_lexical_slot"]+=1
            b["missing_any_lexical_slot"]+=1
            for t in uncovered: missing[t.text]+=1
            missing_per_band[band]["missing"]+=1
        else:
            overall["all_content_tokens_have_candidate"]+=1
            b["all_content_tokens_have_candidate"]+=1
        if any(t.text=="," for t in content):
            overall["with_comma"]+=1;b["with_comma"]+=1
        end=tokens[-1].text if tokens else ""
        if end in (".","!","?"):
            endings["end_"+end]+=1
        report=reader.parse(text,lattice=lat)
        if report.complete:
            overall["success"]+=1;b["success"]+=1
            if not uncovered:
                overall["success_without_missing"]+=1
        else:
            family=failure_family(report.outcome.reason)
            failure[family]+=1
            detail_by_band[band][family]+=1
            if uncovered:
                overall["fail_with_missing"]+=1
            else:
                overall["fail_without_missing"]+=1
            if end=="?": endings["question_failed"]+=1
            if family=="unconsumed" and end=="?":
                endings["question_unconsumed"]+=1
        if i%1000==0:print("DIAGNOSED "+str(i),flush=True)
    return {
        "schema":"seman2-gutenberg-lr-failure-attribution-v1",
        "sample_size":limit,
        "source_books":catalog,
        "selection":"deterministic interleaved book/hash order; train books only, 4-45 tokens",
        "configuration":"SemanCompiledReader(token_only_lattice=True); lookahead=1, checkpoint_budget=0, no construction guard",
        "overall":dict(overall),
        "failure_families":failure.most_common(),
        "punctuation_endings":dict(endings),
        "missing_token_text_top":missing.most_common(25),
        "length_bands":{k:dict(v) for k,v in bands.items()},
        "failure_by_band":{k:dict(v) for k,v in detail_by_band.items()},
        "limitations":[
            "The category of the final stop is one greedy path failure, NOT proof the sentence is outside the grammar.",
            "Missing any lexical token is an independent diagnostic; multiple reasons can co-occur.",
            "No snap cache or teacher training is performed here: raw L-R coverage only.",
            "The sample is deterministic, not a random unbiased fiction benchmark.",
            "No book text included in the aggregate report."
        ]
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--sample",type=int,default=3000)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run(a.wordnet_dir,limit=a.sample)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print("FAILURE_DIAGNOSTIC "+json.dumps({
        "sample_size":result["sample_size"],
        "overall":result["overall"],
        "failure_families":result["failure_families"],
        "missing_token_text_top":result["missing_token_text_top"][:12],
        "punctuation_endings":result["punctuation_endings"],
        "length_bands":result["length_bands"],
    }),flush=True)
