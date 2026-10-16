"""Quick standalone audit of the *whole novels* before grammatical training."""
from collections import Counter
import json
from pathlib import Path
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, TEST_BOOKS, download, extract, length_band

def main():
    books=[]
    for book in (*TRAIN_BOOKS,*TEST_BOOKS):
        core, meta=download(book)
        cases, counts=extract(book,core,length_min=4,length_max=45)
        bands=dict(Counter(length_band(c["tokens"]) for c in cases))
        meta["counts"]=counts
        meta["bands"]=bands
        meta["teacher_eligible_4_to_32"]=sum(c["tokens"]<=32 for c in cases)
        books.append(meta)
        print(f"AUDITED {book.ebook_id}: {book.title} raw={counts['fragments']} candidates={counts['eligible']} teacher_eligible={meta['teacher_eligible_4_to_32']}",flush=True)
    report={
        "source":"Project Gutenberg complete English public-domain classic editions",
        "books":books,
        "total_raw_fragments":sum(b["counts"]["fragments"] for b in books),
        "total_candidate_sentences":sum(b["counts"]["eligible"] for b in books),
        "train_teacher_eligible":sum(b["teacher_eligible_4_to_32"] for b in books if b["role"]=="train"),
        "heldout_candidate_sentences":sum(b["counts"]["eligible"] for b in books if b["role"]=="test"),
        "note":"Counts are tokenizer/regex-heuristic fragments, NOT human validated grammatical sentences. No trainable structures inferred yet.",
    }
    Path("/tmp/gutenberg-corpus-audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print("CORPUS_AUDIT_FINAL "+json.dumps({k:v for k,v in report.items() if k!="books"}),flush=True)

if __name__=="__main__":
    main()
