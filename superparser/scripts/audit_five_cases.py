"""Five-case diagnostic without changing fixed corpus or grammatical scores."""
from __future__ import annotations
import json,signal
from pathlib import Path
from time import perf_counter
from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS
from scripts.diagnose_novel_parses import select_cases,classify
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser,ParserResources

DATA=Path(__file__).resolve().parents[1]/"data"
SAMPLES=(8,76,80,96,100)
def tree(node,text):
    if node is None:return None
    return {
        "rule":node.rule_id,"category":node.category,
        "surface":text[node.start:node.end],
        "features":node.features.as_dict(),
        "children":[tree(c,text) for c in node.children],
    }

class Deadline(Exception):pass
def expire(_s,_f):raise Deadline()

def run():
    cases,_=select_cases(500)
    resources=ParserResources.from_dir(DATA)
    p=Parser(resources,cache_size=64,lexical_left_corner_pruning=True)
    books={x.ebook_id:x for x in TRAIN_BOOKS}
    source_cache={}
    reports=[]
    previous=signal.signal(signal.SIGALRM,expire)
    try:
        for index in SAMPLES:
            c=cases[index]
            if c["book_id"] not in source_cache:
                source_cache[c["book_id"]]=load_cleaned(books[c["book_id"]])[0]
            novel=source_cache[c["book_id"]]
            idx=novel.find(c["source_text"])
            if idx<0:raise AssertionError(f"Cannot find original source span: {index}")
            left=novel.rfind("\n\n",0,idx)
            right=novel.find("\n\n",idx)
            paragraph=novel[left+2 if left>=0 else 0:right if right>=0 else len(novel)]
            context={
                "original_paragraph":paragraph,
                "before":paragraph[:idx-(left+2 if left>=0 else 0)],
                "source_unit":c["source_text"],
                "after":paragraph[idx-(left+2 if left>=0 else 0)+len(c["source_text"]):],
                "balanced_analysis":c["balanced_analysis_text"],
                "balanced_prefix":c["balanced_synthetic_prefix"],
                "balanced_suffix":c["balanced_synthetic_suffix"],
                "semicolon_split":c["semicolon_split"],
            }
            signal.setitimer(signal.ITIMER_REAL,10)
            try:
                prep,lattice,parsed=parse_corpus_case(
                    p,c,max_items=50000,kbest_work_limit=500000)
                relevant=[
                    {"surface":edge.surface,"category":edge.category,
                     "span":[edge.span_start,edge.span_end],
                     "source":edge.source,"lemma":edge.lemma}
                    for edge in lattice.candidates
                    if edge.source in {"lexicalized-placeholder-name",
                        "punctuation-dash","lexicon-multiword"}
                    and (
                        "stage-cutch" in edge.surface.casefold()
                        or "name" in edge.surface.casefold()
                        or edge.source=="punctuation-dash"
                    )
                ]
                report={
                    "status":classify(parsed.completed,parsed.stats),
                    "best_rule":parsed.best().rule_id if parsed.best() else None,
                    "partial_states":parsed.stats.get("partial_states"),
                    "relevant_lexical_candidates":relevant,
                    "best_tree":tree(parsed.best(),lattice.text),
                }
            except Deadline:
                report={"status":"timeout"}
            finally:
                signal.setitimer(signal.ITIMER_REAL,0)
            if index in (8,80):
                text=(c["source_text"] if index==8 else
                      "It is my intention, my dear Copperfield, to educate "
                      "my son for the Church; I will not deny that I should "
                      "be happy, on his account, to attain to eminence.")
                if index==8:
                    text="I could do no less, under these circumstances, than make Mr. Micawber known to Uriah Heep and his mother; which I accordingly did."
                signal.setitimer(signal.ITIMER_REAL,10)
                try:
                    res=p.parse(text,max_items=50000,kbest_work_limit=500000)
                    report["full_sentence"]={
                        "text":text,
                        "completed":res.result.completed,
                        "root":res.result.best().rule_id if res.result.best() else None,
                        "best_tree":tree(res.result.best(),res.lattice.text),
                        "status":classify(res.result.completed,res.result.stats),
                    }
                except Deadline:report["full_sentence"]={"status":"timeout"}
                finally:signal.setitimer(signal.ITIMER_REAL,0)
            reports.append({"index":index,**context,**report})
            print("FIVE_CASE_REPORT",json.dumps(reports[-1],ensure_ascii=False),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGALRM,previous)
    output=Path("five-case-diagnostics.json")
    output.write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":run()
