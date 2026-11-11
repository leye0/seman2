"""Provenance-only audit of source-neighbor context for 500 fixed cases.

Never changes the grammar, quote balancing, Parser.parse result, or success
classification. A neighboring passage is NOT proof of fragment dependency.
"""
from __future__ import annotations
import argparse,json,re
from collections import Counter,defaultdict
from hashlib import sha256
from pathlib import Path
from research.verbnet_lr.clean_novel_corpus import load_cleaned,read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS,CHAPTER,analysis_units
from scripts.diagnose_novel_parses import select_cases,EXPECTED_500_COHORT_SHA256
from seman_parser.sentence_boundaries import (
    split_prose_sentences,split_analysis_units,has_final_punctuation,
)

CONCLUSIVE={"no_structural_root","roots_without_valid_analysis"}
CENSORED={"timeout","forest_budget_exceeded","kbest_budget_exceeded",
          "both_budgets_exceeded"}

def source_contexts(core):
    """Reconstruct ordinals exactly, including skipped corpus candidates."""
    original=list(analysis_units(core))
    result={}
    count=0
    paragraphs=re.split(r"\n\s*\n",core.replace("\r\n","\n"))
    for paragraph_number,paragraph in enumerate(paragraphs):
        lines=[line.strip() for line in paragraph.splitlines() if line.strip()]
        if not lines or CHAPTER.match(lines[0]):
            continue
        joined=re.sub(r"\s+"," "," ".join(lines))
        if not has_final_punctuation(joined) and (
                joined.isupper() or len(joined)<45):
            continue
        sentences=split_prose_sentences(joined)
        for sentence_index,sentence in enumerate(sentences):
            # Same source boundaries as the single active corpus extractor.
            units=split_analysis_units(sentence)
            for part_index,unit in enumerate(units):
                assert count<len(original),(count,len(original))
                assert unit.source_text==original[count].source_text,count
                assert unit.semicolon_split==original[count].semicolon_split,count
                result[count]={
                    "source_text":unit.source_text,
                    "semicolon_split":unit.semicolon_split,
                    "paragraph_index":paragraph_number,
                    "sentence_index_in_paragraph":sentence_index,
                    "semicolon_part_index":part_index,
                    "semicolon_parts":len(units),
                    "full_unsplit_sentence":sentence,
                    "preceding_semicolon_part":units[part_index-1].source_text
                        if part_index else None,
                    "following_semicolon_part":units[part_index+1].source_text
                        if part_index+1<len(units) else None,
                    "previous_sentence_same_paragraph":sentences[sentence_index-1]
                        if sentence_index else None,
                    "next_sentence_same_paragraph":sentences[sentence_index+1]
                        if sentence_index+1<len(sentences) else None,
                }
                count+=1
    assert count==len(original),(count,len(original))
    return result

def surface_signatures(source):
    """Only surface cues, no grammatical truth or automatic repairs."""
    s=source.lstrip(" \t\n\r\"'‘’“”")
    tags=[]
    if re.match(r"^(which|whom|whose)\b",s,re.I):
        tags.append("relative_initial")
    if re.match(r"^(and|but|or|nor)\b",s,re.I):
        tags.append("coordinator_initial")
    if re.match(r"^(and|but|or|nor)\s*,",s,re.I):
        tags.append("coordinator_followed_by_comma")
    if re.match(r"^[a-zA-Z]+ing\b",s):
        tags.append("ing_surface_not_morphologically_verified")
    first=re.search(r"[a-zA-Z]+",s)
    if first and first.group()[0].islower():
        tags.append("lowercase_initial")
    if "--" in source or "—" in source:
        tags.append("em_dash_surface")
    return tags

def fingerprint(cases):
    lines=[json.dumps({
        "index":i,"book_id":c["book_id"],"ordinal":c["ordinal"],
        "band":c["band"],"tokens":c["tokens"],"sentence":c["text"],
        "source_text":c.get("source_text",c["text"]),
        "semicolon_split":bool(c.get("semicolon_split")),
        "synthetic_prefix":c.get("synthetic_prefix",""),
        "synthetic_suffix":c.get("synthetic_suffix",""),
        "synthetic_terminal":bool(c.get("synthetic_terminal")),
    },ensure_ascii=False) for i,c in enumerate(cases)]
    return sha256(("\n".join(lines)+"\n").encode()).hexdigest()

def audit(cases,diagnostics,contexts):
    if len(cases)!=500 or len(diagnostics)!=500:
        raise AssertionError("An exhaustive fixed-500 audit is required")
    digest=fingerprint(cases)
    assert digest==EXPECTED_500_COHORT_SHA256,digest
    output=[]
    groups=Counter()
    counts=defaultdict(Counter)
    examples=defaultdict(list)
    for i,(c,d) in enumerate(zip(cases,diagnostics)):
        if (d["index"]!=i or d["book_id"]!=c["book_id"] or
            d["ordinal"]!=c["ordinal"] or d["sentence"]!=c["text"]):
            raise AssertionError(f"Diagnostic/cohort alignment failure {i}")
        ctx=contexts[c["book_id"]][c["ordinal"]]
        assert ctx["source_text"]==c["source_text"],i
        assert ctx["semicolon_split"]==c["semicolon_split"],i
        status=d["status"]
        group=("complete" if status=="complete" else
               "conclusive_failure" if status in CONCLUSIVE else
               "resource_censored" if status in CENSORED else
               "error" if status=="error" else None)
        if group is None:raise ValueError(status)
        tags=surface_signatures(c["source_text"])
        if ctx["semicolon_parts"]>1:tags.append("actual_semicolon_part")
        if ctx["semicolon_part_index"]>0:
            tags.append("preceded_within_same_semicolon_sentence")
        if ctx["previous_sentence_same_paragraph"] is not None:
            tags.append("preceded_by_sentence_same_paragraph")
        if ctx["next_sentence_same_paragraph"] is not None:
            tags.append("followed_by_sentence_same_paragraph")
        tags=sorted(set(tags))
        groups[group]+=1
        for tag in tags:
            counts[tag][group]+=1
            if group=="conclusive_failure" and len(examples[tag])<20:
                examples[tag].append(i)
        output.append({
            "index":i,"book_id":c["book_id"],"ordinal":c["ordinal"],
            "status":status,"status_group":group,
            "source_text":c["source_text"],
            "context":ctx,"surface_signals":tags,
            "grammatical_fragment_status":"not_determined",
        })
    summary={
        "n":len(output),"cohort_sha256":digest,
        "statuses":dict(groups),
        "signals":{tag:{"status_counts":dict(v),
                        "conclusive_failure_indices":examples[tag]}
                   for tag,v in sorted(counts.items())},
        "original_coverage_unchanged":True,
        "fragment_labels_are_not_gold":True,
        "note":"Source adjacency and surface signatures are not proof of a syntactic fragment.",
    }
    return output,summary

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--diagnostics",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()
    cases,_=select_cases(500)
    diagnostics=[json.loads(s) for s in
        args.diagnostics.read_text(encoding="utf8").splitlines() if s.strip()]
    books={b.ebook_id:b for b in TRAIN_BOOKS}
    contexts={}
    for record in read_manifest()["books"]:
        book=books[record["ebook_id"]]
        text,_=load_cleaned(book)
        contexts[book.ebook_id]=source_contexts(text)
    rows,summary=audit(cases,diagnostics,contexts)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    with (args.out_dir/"context_dependency.jsonl").open("w",encoding="utf8") as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False)+"\n")
    (args.out_dir/"context_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("SOURCE_CONTEXT_SUMMARY",json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
