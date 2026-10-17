"""The deliberately simple Seman2 snap sanity test.

Pass 1: canonical packed VectorGrammar parses each real Gutenberg sentence;
        a *whole grammar tree* is put into the structural snap index.
Pass 2: the exact same ordered corpus is lexed afresh and matched ONLY
        against the stored grammatical structures. No text/result cache, no
        L-R fallback, no new training and no extrapolation.

Report two separate denominators: all inputs and successfully indexed
trees. A parse failure cannot count as a failed recall of a stored tree.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import json
from pathlib import Path
import signal

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract, spread_training
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT=Path(__file__).resolve().parents[1]


class Deadline(Exception):
    pass


@contextmanager
def limit(seconds):
    previous=signal.getsignal(signal.SIGALRM)
    def expired(_sig,_frame):
        raise Deadline()
    signal.signal(signal.SIGALRM,expired)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def samples(count,max_tokens):
    books={}
    for book in TRAIN_BOOKS:
        core,info=download(book)
        rows,_=extract(book,core,length_min=4,length_max=max_tokens)
        books[book.ebook_id]=rows
    selected=[]
    distinct=set()
    for row in spread_training(books,sum(map(len,books.values()))):
        fingerprint=" ".join(row["text"].casefold().split())
        if fingerprint in distinct:
            continue
        distinct.add(fingerprint)
        selected.append(row)
        if len(selected)>=count:
            break
    if len(selected)!=count:
        raise RuntimeError(f"Insufficient corpus examples: {len(selected)}")
    return selected


def run(wordnet_dict, *, count=200, max_tokens=12,
        max_items=30000, timeout=1.5):
    if min(count,max_tokens,max_items)<=0 or timeout<=0:
        raise ValueError("All budgets must be positive")
    corpus=samples(count,max_tokens)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dict)
    parser=Parser(resources,cache_size=0,max_items=max_items)
    memory=FullStructureSnapIndex(resources)
    trained_ids={}
    first=Counter()
    reasons=Counter()

    # PASS 1: genuine grammar search. The single-token lexical view is an
    # explicit limitation of the existing whole-tree snap index.
    for i,row in enumerate(corpus):
        sentence=row["text"]
        lattice=build_lattice(sentence,resources.lexicon,multiword_max=1)
        first["input"]+=1
        try:
            with limit(timeout):
                parsed=parser._vector_grammar.parse_lattice(
                    lattice,beam=parser.beam,max_items=max_items,
                    goal_category=parser.goal_category)
                tree=parsed.best() if parsed.completed else None
        except Deadline:
            first["parse_timeout"]+=1
            continue
        if tree is None:
            first["not_completed"]+=1
            continue
        first["complete"]+=1
        try:
            template=memory.observe(tree,lattice=lattice,evidence="candidate")
            trained_ids[i]=template
            first["stored"]+=1
        except (ValueError,OverflowError) as exc:
            first["not_indexable"]+=1
            reasons[type(exc).__name__+":"+str(exc)[:80]]+=1
        if (i+1)%50==0:
            print("TRAIN",i+1,dict(first),flush=True)

    print("PASS_ONE",json.dumps({
        "total":len(corpus),"complete":first["complete"],
        "stored":first["stored"],"unique_templates":len(memory.templates),
        "failures":dict(reasons),
    }),flush=True)

    # PASS 2: ONLY the structural snap matcher. It never reparses the input
    # with VectorGrammar or any other parser and cannot train on pass two.
    second=Counter()
    failed_recall=[]
    unexpected=[]
    for i,row in enumerate(corpus):
        lattice=build_lattice(row["text"],resources.lexicon,multiword_max=1)
        try:
            with limit(timeout):
                match=memory.match(
                    lattice,max_templates_checked=512,max_states=16384,
                    max_variants=32,max_reductions=8192)
        except Deadline:
            second["match_timeout"]+=1
            if i in trained_ids:
                failed_recall.append({"book":row["book_id"],
                    "ordinal":row["ordinal"],"reason":"match_timeout"})
            continue
        second["input"]+=1
        second["any_snap"]+=int(match.complete)
        second["incomplete_search"]+=int(match.incomplete)
        expected=trained_ids.get(i)
        if expected is None:
            second["untrained_inputs"]+=1
            second["snap_without_own_tree"]+=int(match.complete)
        else:
            second["eligible_stored"]+=1
            ids={m.template_id for m in match.matches}
            own_found=expected in ids
            second["own_template_snapped"]+=int(own_found)
            second["any_snap_of_stored"]+=int(match.complete)
            if not own_found:
                failed_recall.append({
                    "book":row["book_id"],"ordinal":row["ordinal"],
                    "template_id":expected,
                    "candidate_templates":match.candidate_templates,
                    "checked_templates":match.checked_templates,
                    "incomplete":match.incomplete,"reason":match.reason,
                })
        if (i+1)%50==0:
            print("REPLAY",i+1,dict(second),flush=True)

    result={
        "schema":"seman2-two-pass-structural-snap-only-v1",
        "description":"Same real Gutenberg sentences twice; first vector grammar, then only grammar-tree structural matcher; no text cache",
        "configuration":{"sentences":count,"max_tokens":max_tokens,
                         "max_items":max_items,"timeout_s":timeout},
        "first_pass":dict(first),
        "unique_grammatical_structures":len(memory.templates),
        "second_pass":dict(second),
        "recall_of_stored_pct":round(100*second["own_template_snapped"]/
                                  first["stored"],3) if first["stored"] else None,
        "fraction_of_all_sentences_that_snap_pct":
            round(100*second["any_snap"]/count,3),
        "failure_reasons":dict(reasons),
        "failed_recall_positions":failed_recall[:30],
        "remarks":[
            "Only trees completely analyzed and indexed on pass one can be required to recall on pass two.",
            "The structural matcher stores rule and POS-tree patterns, never raw text or saved ParseResults.",
            "The same exact input is repeated; this is a memorization sanity check, not cross-author generalization.",
            "Multiword leaves are unsupported by this particular whole-tree index; such trees are counted as not_indexable.",
            "A template is a licensed candidate derivation, not an independently verified correct tree.",
            "Matcher budgets and timeouts are explicit and misses are reported, not silently converted to correct parses.",
        ],
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--wordnet-dir",required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--count",type=int,default=200)
    p.add_argument("--max-tokens",type=int,default=12)
    p.add_argument("--max-items",type=int,default=30000)
    p.add_argument("--timeout",type=float,default=1.5)
    a=p.parse_args()
    report=run(a.wordnet_dir,count=a.count,max_tokens=a.max_tokens,
               max_items=a.max_items,timeout=a.timeout)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print("FINAL",json.dumps({
        "count":report["configuration"]["sentences"],
        "first":report["first_pass"],
        "unique_templates":report["unique_grammatical_structures"],
        "second":report["second_pass"],
        "recall_of_stored_pct":report["recall_of_stored_pct"],
        "all_sentence_snap_pct":report["fraction_of_all_sentences_that_snap_pct"],
        "failed_examples":report["failed_recall_positions"][:5]
    },separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
