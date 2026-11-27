"""Resolve frozen Novel-1000 v3 source anchors without the old parser."""
from hashlib import sha256
import json
from pathlib import Path
from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input

DIRECTORY=Path(__file__).resolve().parents[1]/"research"/"novel_source_reporting_v3"
EXPECTED_MANIFEST="93bb915a30a956fef8c465a7dd684e57cfd2b2866f225409c9fd4686d0b2e5af"
def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def pinned_novel_sources():
    manifest=json.loads((DIRECTORY/"source-manifest.json").read_text())
    if digest(manifest)!=EXPECTED_MANIFEST:
        raise ValueError("Novel manifest changed")
    anchors=json.loads((DIRECTORY/"anchors.json").read_text())
    bodies,rows,editions={}, {}, []
    for book in sorted(TRAIN_BOOKS,key=lambda x:x.ebook_id):
        body,info=load_cleaned(book)
        bodies[book.ebook_id]=body
        editions.append({"book_id":book.ebook_id,"sha256":info["sha256"]})
        cases,_=extract(book,body,length_min=4,length_max=32)
        for c in cases:
            rows[(book.ebook_id,*c["structural_core_source_span"])]=c
    if editions!=manifest["editions"]:
        raise ValueError("Novel editions changed")
    result=[]
    for group in ("500","600","700","800","900","1000"):
        pin=manifest["cohorts"][group]
        if len(anchors[group])!=pin["size"] or digest([manifest["schema"],anchors[group]])!=pin["cohort_sha256"]:
            raise ValueError(f"Anchor group drift: {group}")
        for i,book,para,a,b,band,source_sha in anchors[group]:
            c=rows[(book,a,b)]
            text=prepare_corpus_input(c).analysis_text
            if (c["structural_paragraph_index"]!=para or sha256(text.encode()).hexdigest()!=source_sha
                or " ".join(bodies[book][a:b].split())!=text):
                raise ValueError(f"Source changed at Q3-{i}")
            result.append((f"Q3-{i}",c))
    if [name for name,c in result]!=[f"Q3-{i}" for i in range(1,1001)]:
        raise ValueError("Expected exactly the 1000 frozen source IDs")
    return EXPECTED_MANIFEST,result
