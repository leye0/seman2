"""Held-out learning curves from AUTHENTIC, pinned UD English-EWT sentences.

Training: 50 existing DEV sentences plus 0/100/300/600 deterministic
sentences from the separate UD English-EWT TRAIN corpus. Evaluation uses only
the 50 VALIDATION and 20 HOLDOUT sentences from Seman2, plus its fixed 24
negative cases. These evaluation texts and annotations NEVER enter training.

Comparison: bounded Earley teacher on every external training sentence vs
sampling one tenth into a separately stored cache (same initial 50 DEV
examples). Both teachers only produce grammar-unified candidates, not gold.
NO production parser changes; no implicit background execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex, SnappingResearchReader
from research.verbnet_lr.sampled_teacher import VerificationSamplingQueue
from research.verbnet_lr.packed_witness import seek_packed_witness
from research.verbnet_lr.construction_guard import ConstructionGuard
from scripts.benchmark_ud_ewt_lr import REVISION, read_conllu
from scripts.benchmark_verbnet_reader import syntax_assertions
from seman_parser.engine import ParserResources
from seman_parser.reading_kernel_compiled_adapter import SemanCompiledReader
from seman_parser.reading_kernel_compiled import Event
from seman_parser.segmentation import tokenize, build_lattice

ROOT = Path(__file__).resolve().parents[1]
TRAIN_URL = (
    "https://raw.githubusercontent.com/UniversalDependencies/UD_English-EWT/"
    + REVISION + "/en_ewt-ud-train.conllu"
)


def _quantile(nums, q):
    if not nums:
        return None
    values = sorted(nums)
    return round(values[min(len(values)-1, int((len(values)-1)*q))], 5)


def _gold(case, report, path):
    if path != "snap":
        return syntax_assertions(case, report)["pass"]
    events = []
    def visit(node):
        if node.lexical_candidate is not None:
            candidate = node.lexical_candidate
            events.append(Event(0,candidate.surface,"CONSUME",
                                candidate.category,""))
        for ch in node.children:
            visit(ch)
        if node.rule_id:
            events.append(Event(0,"","COMPLETE",node.category,node.rule_id))
    visit(report.item)
    from types import SimpleNamespace
    proxy = SimpleNamespace(complete=True,item=report.item,
                            outcome=SimpleNamespace(events=events))
    return syntax_assertions(case,proxy)["pass"]


def _train_teacher(index, lattice, *, seconds, mirror=None):
    guard = ConstructionGuard(modal_forms={
        c.surface.casefold() for c in lattice.candidates if c.category == "MODAL"})
    report = seek_packed_witness(
        index.resources.grammar,lattice,
        max_seconds=seconds,max_items=60_000,
        max_expansions=30_000,max_paths_per_item=4,
        max_backpointers=4,validate_tree=guard.validate,
        return_compact_node=True)
    if report["status"] != "FOUND":
        return report["status"]
    item = index._materializer._materialize(report["witness_node"])
    try:
        index.observe(item,lattice=lattice,evidence="grammar_witness")
        if mirror is not None:
            # Exactly the SAME proven tree, not a re-ranked (possibly
            # different) template on a second read of the same sentence.
            mirror.observe(item,lattice=lattice,evidence="grammar_witness")
    except ValueError:
        return "UNSUPPORTED"
    return "ADDED"


def _evaluate(index, resources, cases, negatives):
    machine = SnappingResearchReader(
        resources,index=index,
        fallback=SemanCompiledReader(resources,token_only_lattice=True))
    hits=0
    gold=0
    completions=0
    times=[]
    for case in cases:
        started=perf_counter()
        report,path=machine.parse(case["text"])
        times.append((perf_counter()-started)*1000)
        completions+=int(report.complete)
        hits+=int(path=="snap")
        gold+=int(_gold(case,report,path) is True)
    false_accepts = 0
    for case in negatives:
        report,_ = machine.parse(case["text"])
        false_accepts+=int(report.complete)
    return {
        "templates":len(index.templates),
        "witness_templates":index.summary()["grammar_witness_templates"],
        "hits":hits,"completed":completions,
        "explicit_gold_pass":gold,
        "false_accepts_24":false_accepts,
        "hybrid_p50_ms":_quantile(times,.5),
        "hybrid_p95_ms":_quantile(times,.95),
    }


def run(*,wordnet_dir,max_external=600,milestones=(0,100,300,600),
        external_seconds=.16,dev_seconds=.35):
    milestones=tuple(sorted(set(milestones)))
    if (not milestones or milestones[0]!=0 or milestones[-1]>max_external
            or max_external<1 or external_seconds<=0 or dev_seconds<=0):
        raise ValueError("Invalid limits or milestones")
    local_rows=[json.loads(x) for x in (
        ROOT/"data/syntax_correctness_validation.jsonl").read_text().splitlines()
        if x.strip()]
    dev=[r for r in local_rows if r["split"]=="dev"]
    evaluation=[r for r in local_rows if r["split"]!="dev"]
    neg=[json.loads(x) for x in (
        ROOT/"research/verbnet_lr/negative_minimal_pairs.jsonl"
        ).read_text().splitlines() if x.strip()]
    # Strong text-level leakage exclusion, including negative contrasts.
    forbidden={r["text"].strip().casefold() for r in local_rows}
    forbidden.update(r["text"].strip().casefold() for r in neg)
    forbidden.update(r["contrast"].strip().casefold() for r in neg)
    request=Request(TRAIN_URL,headers={"User-Agent":"Seman2-syntax-snap-study"})
    with urlopen(request,timeout=90) as response:
        corpus=response.read().decode("utf8")
    seen=set()
    eligible=[]
    for case in read_conllu(corpus):
        text=case["text"].strip()
        normalized=text.casefold()
        token_count=len(tokenize(text))
        if (normalized in forbidden or normalized in seen
                or not text.isascii() or not 4<=token_count<=18):
            continue
        seen.add(normalized)
        eligible.append(case)
    selected=sorted(eligible,key=lambda c:
                    sha256(c["id"].encode()).hexdigest())[:max_external]
    if len(selected)<max_external:
        raise RuntimeError("Insufficient nonoverlapping authentic EWT train cases")
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    all_index=FullStructureSnapIndex(resources)
    tenth_index=FullStructureSnapIndex(resources)
    lr=SemanCompiledReader(resources,token_only_lattice=True)
    dev_stats=Counter()
    for case in dev:
        text=case["text"]
        lattice=build_lattice(text,resources.lexicon,multiword_max=1)
        baseline=lr.parse(text,lattice=lattice)
        if baseline.complete:
            for index in (all_index,tenth_index):
                try:
                    index.observe(baseline.item,lattice=lattice,evidence="candidate")
                except ValueError:
                    dev_stats["lr_unsupported"]+=1
            dev_stats["lr_complete"]+=1
        status=_train_teacher(all_index,lattice,seconds=dev_seconds,
                              mirror=tenth_index)
        dev_stats["teacher_"+status]+=1
    # A fair learning-curve comparison MUST have the same exact initial
    # structures, not merely similar totals. The only difference between
    # caches after this point is external teacher sampling frequency.
    assert all_index._by_shape == tenth_index._by_shape
    assert all_index.summary() == tenth_index.summary()
    sampler=VerificationSamplingQueue(every=10,phase=0,max_pending=20)
    checkpoints=[]
    external_stats=Counter()
    def record(n):
        checkpoints.append({
            "external_training_sentences_seen":n,
            "all_teacher":_evaluate(all_index,resources,evaluation,neg),
            "ten_percent_teacher":_evaluate(tenth_index,resources,evaluation,neg),
            "sampled_teacher":sampler.summary(),
            "external_evidence":dict(external_stats),
        })
    record(0)
    for number,case in enumerate(selected,1):
        text=case["text"]
        lattice=build_lattice(text,resources.lexicon,multiword_max=1)
        status=_train_teacher(all_index,lattice,seconds=external_seconds)
        external_stats[status]+=1
        sampler.enqueue(text,lattice)
        if number % 10 == 0:
            sampler.drain_teacher(tenth_index,max_cases=4,max_seconds=external_seconds)
        if number in milestones:
            while sampler.pending:
                sampler.drain_teacher(tenth_index,max_cases=10,
                                      max_seconds=external_seconds)
            record(number)
    return {
        "schema":"seman2-authentic-fulltree-learning-curve-v1",
        "training_source":TRAIN_URL,
        "train_revision":REVISION,
        "selection":"SHA256 EWT TRAIN sent_id, ASCII 4-18 tokens; text disjoint from entire Seman2 corpus + negatives/contrasts",
        "external_available":len(eligible),
        "external_trained":len(selected),
        "dev_cases":len(dev),
        "evaluation_cases":len(evaluation),
        "negative_cases":len(neg),
        "teacher_seconds_per_external":external_seconds,
        "dev_seed":dict(dev_stats),
        "checkpoints":checkpoints,
        "limitations":[
            "EWT dependency gold annotations are NEVER read for training; texts only.",
            "Teacher evidence is grammar-unified, NOT full natural-language gold.",
            "EWT train and Seman2 validation/holdout originate from different distributions.",
            "The tenth-sentence sampler examines every tenth external observation offline, not within parse().",
            "Selected lexical candidates remain all available for snapping and grammatical unification.",
            "Absent external teacher derivations never count as ungrammatical.",
            "No on-disk index or million-pattern scaling claimed.",
        ]
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--max-external",type=int,default=600)
    p.add_argument("--milestones",default="0,100,300,600")
    p.add_argument("--external-seconds",type=float,default=.16)
    p.add_argument("--dev-seconds",type=float,default=.35)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=run(wordnet_dir=a.wordnet_dir,max_external=a.max_external,
               milestones=tuple(int(x) for x in a.milestones.split(",")),
               external_seconds=a.external_seconds,dev_seconds=a.dev_seconds)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"checkpoints":result["checkpoints"],
                      "dev_seed":result["dev_seed"]},indent=2))
