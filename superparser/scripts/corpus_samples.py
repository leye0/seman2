"""Deterministic novel cohorts for current Layer 1 regression/benchmarking.

Uses the checked-in *cleaned* Gutenberg texts. Never rewrites the corpus or
strips quotations; the per-book manifest provides integrity information.
"""
from __future__ import annotations

from research.verbnet_lr.clean_novel_corpus import load_cleaned, read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract

BANDS=(("04-08",4,8),("09-16",9,16),("17-24",17,24),("25-32",25,32))


def sample_spread(rows,n):
    if n<0 or n>len(rows):
        raise ValueError(f"Need {n} distinct sentences, available {len(rows)}")
    indices=[((2*i+1)*len(rows))//(2*n) for i in range(n)] if n else []
    if len(set(indices))!=n:
        raise AssertionError("Duplicate sample index")
    return [rows[i] for i in indices]


def choose_cases(per_book_per_band):
    books={book.ebook_id:book for book in TRAIN_BOOKS}
    selected=[]
    source=[]
    for record in read_manifest()["books"]:
        book=books[record["ebook_id"]]
        text,info=load_cleaned(book)
        rows,_=extract(book,text,length_min=4,length_max=32)
        for band,lower,upper in BANDS:
            pool=[r for r in rows if lower<=r["tokens"]<=upper]
            amount=min(per_book_per_band,len(pool))
            selected.extend({**r,"band":band}
                            for r in sample_spread(pool,amount))
            source.append({
                "book_id":book.ebook_id,"title":book.title,
                "band":band,"eligible":len(pool),
                "sampled":amount,"sha256":info["sha256"],
            })
    return selected,source
