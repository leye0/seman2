"""Source-anchored real-novel grammar witnesses, independent of cohort sampling.

The integer IDs below identify attested test cases from pre-migration research.
They are **not indices into the current 500-case benchmark**. Each fixture is
resolved from the checked-in original cleaned novel with the ONE active
extractor, and its balanced quotation provenance is generated there.
A missing or newly merged source unit FAILS rather than secretly asking the
obsolete splitter for an old clipped sentence.
"""
from __future__ import annotations

from functools import lru_cache

from research.verbnet_lr.clean_novel_corpus import load_cleaned
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS, extract

# Historical numeric names retained only as fixture IDs for grammar tests.
# Full excerpts are checked by unique source-text starts, never by corpus rank.
ATTESTED_STARTS = {
    99: (766, "I should have gone to bed with a sore heart indeed"),
    112: (766, "Our instructions to Mr. Dick were that he should copy exactly"),
    200: (1342, "“I had not at that time the honour of knowing any lady"),
    202: (1342, "To persuade him against returning into Hertfordshire,"),
    209: (1342, "It is really too great a violation of decency, honour,"),
    212: (1342, "We were married, you know, at St. Clement's,"),
    215: (1342, "It would vex me, indeed, to see you again the dupe"),
    232: (1342, "She not unfrequently stopped at the Parsonage,"),
    239: (1342, "Yet time and her aunt moved slowly--"),
    248: (1342, "The turn of your countenance I shall never forget,"),
    317: (84, "Unless I had been animated by an almost supernatural enthusiasm,"),
    340: (84, "I broke from the house angry and disturbed"),
    354: (84, "This valley is more wonderful and sublime,"),
    356: (84, "This hovel however, joined a cottage of a neat"),
    357: (84, "The youth and his companion had each of them several names,"),
    359: (84, '"The Turk allowed this intimacy to take place'),
    370: (84, "She was there, lifeless and inanimate,"),
    371: (84, "But to a Genevan magistrate, whose mind was occupied"),
    392: (120, '"Ten to one this is a trick."'),
    414: (120, "and now here on my own account, in a manner of speaking."),
    441: (120, "In the meantime the supervisor rode on,"),
    445: (120, "Aboard ship he carried his crutch by a lanyard"),
    449: (120, "but the murderer minded him not a whit,"),
    463: (120, "You've neither sense nor memory, and I leave it"),
    467: (120, "Every thought of his soul had been set full-stretch,"),
    480: (120, "'As for you, Benjamin Gunn,' says they,"),
    485: (120, "As soon as the sun had climbed above our girdle of trees,"),
}


@lru_cache(maxsize=1)
def select_attested_cases(count: int = 500):
    """Resolve old fixture IDs by stable novel text, not the active cohort.

    Matches are intentionally strict. If segmentation merges or changes one
    old example, repair that test against the correct contiguous source,
    rather than reintroducing an alternate historical splitting algorithm.
    """
    if count != 500:
        raise ValueError("Only the historical fixture ID set is supported")
    books = {b.ebook_id: b for b in TRAIN_BOOKS}
    cases = {}
    for ebook_id in sorted({book for book, _ in ATTESTED_STARTS.values()}):
        text, _ = load_cleaned(books[ebook_id])
        rows, _ = extract(books[ebook_id], text, length_min=1, length_max=1000)
        for fixture_id, (source_book, prefix) in ATTESTED_STARTS.items():
            if source_book != ebook_id:
                continue
            matches = [row for row in rows if row["source_text"].startswith(prefix)]
            if len(matches) != 1:
                raise AssertionError(
                    f"Attested fixture {fixture_id}: expected one current "
                    f"source unit starting {prefix!r}, got {len(matches)}"
                )
            cases[fixture_id] = matches[0]
    assert len(cases) == len(ATTESTED_STARTS)
    return cases, []
