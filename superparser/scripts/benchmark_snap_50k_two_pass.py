"""Two consecutive, identical Gutenberg passes: learn whole grammar trees, then SNAP.

This is the *structural cache* and real VectorGrammar, not text-result memoization
or the weak single-continuation reader. Pass 2 measures lexical+snap+vector
fallback on every sentence and audits fidelity against the first-pass tree.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import signal
from time import perf_counter

from research.verbnet_lr.full_structure_snap import FullStructureSnapIndex
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, download, extract, spread_training
from seman_parser.engine import Parser, ParserResources
from seman_parser.segmentation import build_lattice

ROOT = Path(__file__).resolve().parents[1]


class Deadline(Exception):
    pass


@contextmanager
def deadline(seconds):
    previous=signal.getsignal(signal.SIGALRM)
    def expire(_sig,_frame):
        raise Deadline()
    signal.signal(signal.SIGALRM,expire)
    signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)


def canonical(value):
    return json.dumps(value,sort_keys=True,default=str,separators=(",",":"))


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def lexical_tree(tree):
    """Compare every selected original word reading: span/POS/lemma/sense/features."""
    if tree is None:
        return ()
    if tree.lexical_candidate is not None:
        c=tree.lexical_candidate
        return ((tree.start,tree.end,c.category,c.lemma,
                 tuple(c.sense_ids),c.features.as_dict()),)
    return tuple(x for child in tree.children for x in lexical_tree(child))


def entire_tree(tree):
    if tree is None:
        return None
    if tree.lexical_candidate is not None:
        c=tree.lexical_candidate
        leaf=(c.category,c.lemma,tuple(c.sense_ids),c.features.as_dict())
    else:
        leaf=None
    return (tree.category,tree.start,tree.end,tree.rule_id,
            tree.features.as_dict(),tree.syntax.as_dict(),leaf,
            [entire_tree(ch) for ch in tree.children])


def whole_lexical_lattice(lattice):
    # All lexical alternatives, not only the best analyzed sense.
    return digest([
        (c.span_start,c.span_end,c.category,c.lemma,tuple(c.sense_ids),
         c.features.as_dict(),c.syntactic_constraints,c.score)
        for c in lattice.candidates
    ])


def quantile(values,p):
    if not values:
        return None
    data=sorted(values)
    position=(len(data)-1)*p
    low=int(position)
    high=min(low+1,len(data)-1)
    return round(data[low]+(position-low)*(data[high]-data[low]),4)


def spread_novel_corpus(target,max_tokens):
    novels={}
    sources=[]
    for book in TRAIN_BOOKS:
        corpus,info=download(book)
        rows,_=extract(book,corpus,length_min=4,length_max=max_tokens)
        novels[book.ebook_id]=rows
        sources.append((book.ebook_id,info["sha256"],len(rows)))
        print("BOOK",book.ebook_id,len(rows),flush=True)
    # Extra candidate positions allow us to de-duplicate without ending below
    # exactly 50,000.
    selected=[]
    seen=set()
    for case in spread_training(novels,sum(len(x) for x in novels.values())):
        normalized=" ".join(case["text"].casefold().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append(case)
        if len(selected)==target:
            break
    if len(selected)!=target:
        raise RuntimeError(f"Only {len(selected)} distinct sentences, need {target}")
    print("CORPUS",json.dumps({"target":target,"actual":len(selected),
                               "books":sources,"max_tokens":max_tokens}),flush=True)
    return selected,sources


def run(wordnet_dir,*,size=50000,max_tokens=32,max_items=20000,
        parse_timeout_s=.35,match_timeout_s=.20,checkpoint=1000,out):
    if min(size,max_tokens,max_items,checkpoint)<=0 or min(
        parse_timeout_s,match_timeout_s)<=0:
        raise ValueError("All budgets must be positive")
    sentences,sources=spread_novel_corpus(size,max_tokens)
    resources=ParserResources.from_dir(ROOT/"data",wordnet_dict=wordnet_dir)
    engine=Parser(resources,cache_size=0,max_items=max_items)
    memory=FullStructureSnapIndex(resources)
    original={}
    first=Counter()
    second=Counter()
    durations=defaultdict(list)
    by_length=defaultdict(Counter)
    cumulative_original=0.
    cumulative_baseline_replayed=0.
    cumulative_second=0.
    training_index_ms=0.
    replayed_stored=0
    curve=[]

    # Pass 1: always genuine VectorGrammar. No grammar analysis is invented
    # when the vector parse is unknown or times out.
    for i,sentence in enumerate(sentences):
        started=perf_counter()
        lattice=build_lattice(sentence["text"],resources.lexicon,multiword_max=1)
        lexing_ms=(perf_counter()-started)*1000.
        outcome=None
        parse_start=perf_counter()
        try:
            with deadline(parse_timeout_s):
                report=engine._vector_grammar.parse_lattice(
                    lattice,beam=engine.beam,max_items=max_items,
                    goal_category=engine.goal_category)
                outcome=report.best() if report.completed else None
        except Deadline:
            first["timeout"]+=1
        parsing_ms=(perf_counter()-parse_start)*1000.
        total_ms=lexing_ms+parsing_ms
        cumulative_original+=total_ms
        durations["pass1"].append(total_ms)
        first["seen"]+=1
        first["completed"]+=int(outcome is not None)
        if outcome is not None:
            start=perf_counter()
            try:
                template_id=memory.observe(outcome,lattice=lattice,
                                           evidence="candidate")
                original[i]={
                    "template_id":template_id,
                    "lexical_hash":digest(lexical_tree(outcome)),
                    "tree_hash":digest(entire_tree(outcome)),
                    "lattice_hash":whole_lexical_lattice(lattice),
                }
                first["stored"]+=1
            except (ValueError,OverflowError) as error:
                first["not_indexable"]+=1
                first["not_indexable_"+type(error).__name__]+=1
            training_index_ms+=(perf_counter()-start)*1000.
        if (i+1)%checkpoint==0:
            print("TRAIN",json.dumps({"seen":i+1,"completed":first["completed"],
                "stored":first["stored"],"timeout":first["timeout"],
                "unique_templates":len(memory.templates)}),flush=True)
    print("FIRST",json.dumps(dict(first)),flush=True)

    # Pass 2: structural trie first, actual vector parsing ONLY on a miss.
    # An incorrect candidate from the matcher is counted explicitly; no
    # benchmark oracle makes decisions for the runtime.
    for i,sentence in enumerate(sentences):
        total_start=perf_counter()
        lex_start=perf_counter()
        lattice=build_lattice(sentence["text"],resources.lexicon,multiword_max=1)
        second_lex_ms=(perf_counter()-lex_start)*1000
        snap=None
        match_start=perf_counter()
        try:
            with deadline(match_timeout_s):
                snap=memory.match(lattice,max_templates_checked=512,
                                  max_states=16384,max_variants=32,
                                  max_reductions=8192)
        except Deadline:
            second["match_timeout"]+=1
        match_ms=(perf_counter()-match_start)*1000
        second["seen"]+=1
        cumulative_baseline_replayed+=durations["pass1"][i]
        replayed_stored+=int(i in original)
        if snap is not None and snap.complete:
            second["snap_hit"]+=1
            second["snap_incomplete_search"]+=int(snap.incomplete)
            stored=original.get(i)
            if stored is not None:
                ids={m.template_id for m in snap.matches}
                own=stored["template_id"] in ids
                second["own_template_recovered"]+=int(own)
                own_match=next((m for m in snap.matches
                                if m.template_id==stored["template_id"]),None)
                if own_match is not None:
                    second["own_lexical_identical"]+=int(
                        digest(lexical_tree(own_match.item))==stored["lexical_hash"])
                    second["own_tree_identical"]+=int(
                        digest(entire_tree(own_match.item))==stored["tree_hash"])
                chosen=snap.matches[0].item
                second["chosen_lexical_identical"]+=int(
                    digest(lexical_tree(chosen))==stored["lexical_hash"])
                second["chosen_tree_identical"]+=int(
                    digest(entire_tree(chosen))==stored["tree_hash"])
                second["fresh_lattice_identical"]+=int(
                    whole_lexical_lattice(lattice)==stored["lattice_hash"])
            else:
                second["hit_no_prior_stored_tree"]+=1
        else:
            second["fallback"]+=1
            parse_start=perf_counter()
            try:
                with deadline(parse_timeout_s):
                    fallback=engine._vector_grammar.parse_lattice(
                        lattice,beam=engine.beam,max_items=max_items,
                        goal_category=engine.goal_category)
                    _=fallback.best() if fallback.completed else None
            except Deadline:
                second["fallback_timeout"]+=1
            second["fallback_ms"]+=int((perf_counter()-parse_start)*1000)
        total_ms=(perf_counter()-total_start)*1000.
        cumulative_second+=total_ms
        durations["pass2"].append(total_ms)
        durations["snap_search"].append(match_ms)
        durations["pass2_lexical"].append(second_lex_ms)
        band="04-12" if sentence["tokens"]<=12 else (
            "13-24" if sentence["tokens"]<=24 else "25-32")
        by_length[band]["seen"]+=1
        by_length[band]["snap_hit"]+=int(snap is not None and snap.complete)
        by_length[band]["stored"]+=int(i in original)
        if (i+1)%checkpoint==0 or i+1==size:
            saved=cumulative_baseline_replayed-cumulative_second
            point={
                "sentences":i+1,
                "stored":replayed_stored,
                "snap_hits":second["snap_hit"],
                "recall_of_prior_stored":second["own_template_recovered"],
                "lexical_identical":second["chosen_lexical_identical"],
                "baseline_parse_total_s":round(cumulative_baseline_replayed/1000,3),
                "replay_snap_plus_fallback_total_s":round(cumulative_second/1000,3),
                "net_saved_s":round(saved/1000,3),
                "pass2_saved_pct":round(100*saved/cumulative_baseline_replayed,3),
                "two_pass_net_saved_pct":round(
                    100*(saved-training_index_ms)/
                    (2*cumulative_baseline_replayed),3),
                "p50_replay_ms":quantile(durations["pass2"],.5),
                "p75_replay_ms":quantile(durations["pass2"],.75),
                "p90_replay_ms":quantile(durations["pass2"],.9),
            }
            curve.append(point)
            print("CURVE",json.dumps(point,separators=(",",":")),flush=True)
            # Save durable checkpoints even when the CI run later hits limits.
            result={
                "schema":"seman2-50k-identical-vector-structural-snap-v1",
                "complete":i+1==size,
                "corpus":{"target":size,"processed_second_pass":i+1,
                          "max_tokens":max_tokens,"books":sources},
                "limits":{"max_items":max_items,
                          "parse_timeout_s":parse_timeout_s,
                          "match_timeout_s":match_timeout_s},
                "first_pass":dict(first),
                "second_pass":dict(second),
                "unique_templates":len(memory.templates),
                "learning_index_ms":round(training_index_ms,2),
                "by_length":{k:dict(v) for k,v in by_length.items()},
                "time_percentiles_ms":{
                    name:{p:quantile(t,pct) for p,pct in (
                        ("p50",.5),("p75",.75),("p90",.9))}
                    for name,t in durations.items()},
                "curve":curve,
                "clarifications":[
                    "Structural rule/POS patterns only; no text or ParseResult cache.",
                    "Snap hit is not a guarantee of lexical or full-tree parity.",
                    "Lexical parity means equality to the originally selected parse, not independent human gold.",
                    "The canonical vector baseline uses the same one-token lattice, no multiwords.",
                    "Replaying unknown or failed originals still counts as input and uses fallback.",
                    "Pass 2 timings include lexing, trie matching and fallback on misses.",
                    "The full two-pass saving subtracts the incremental indexing overhead.",
                    "Timeouts are counted as failures, not grammatical impossibilities.",
                ],
            }
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--wordnet-dir",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--size",type=int,default=50000)
    ap.add_argument("--max-tokens",type=int,default=32)
    ap.add_argument("--max-items",type=int,default=20000)
    ap.add_argument("--parse-timeout",type=float,default=.35)
    ap.add_argument("--match-timeout",type=float,default=.20)
    ap.add_argument("--checkpoint",type=int,default=1000)
    args=ap.parse_args()
    r=run(args.wordnet_dir,size=args.size,max_tokens=args.max_tokens,
          max_items=args.max_items,parse_timeout_s=args.parse_timeout,
          match_timeout_s=args.match_timeout,checkpoint=args.checkpoint,
          out=args.out)
    f=r["first_pass"];s=r["second_pass"]
    print("FINAL",json.dumps({
        "target":args.size,"complete":r["complete"],"stored":f["stored"],
        "snap_hits":s["snap_hit"],"stored_recalled":s["own_template_recovered"],
        "chosen_lexical_equal":s["chosen_lexical_identical"],
        "chosen_tree_equal":s["chosen_tree_identical"],
        "time":r["curve"][-1],
    },separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
