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
    434: (120, "Skeleton Island E.S.E. and by E. Ten feet."),
    438: (120, "Now, Mrs. Hawkins, just you run upstairs to your husband"),
}


@lru_cache(maxsize=1)
def select_attested_cases(count: int = 500):
    """Historical grammar witnesses, frozen by source text, NOT current units.

    Do not force modern corpus segmentation to reproduce old fragments simply
    because grammatical-tree tests originally used an old 500-case index.
    These immutable source quotations are test data, never production inputs
    and never used for the current benchmark.
    """
    if count != 500:
        raise ValueError("Historical grammar witnesses require count=500")
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parent / "data" / "attested_source_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = {int(i): row for i, row in payload["cases"].items()}
    for i, (book_id, prefix) in ATTESTED_STARTS.items():
        if i not in cases or cases[i]["book_id"] != book_id:
            raise AssertionError(f"Historical grammar fixture {i} not found")
        if not cases[i]["source_text"].startswith(prefix):
            raise AssertionError(f"Historical grammar fixture {i} changed")
    return cases, []
