"""Audited, local public-domain novel corpus for grammatical-analysis experiments.

Old benchmarking routines retain their *original* downloaded Gutenberg sources.
Opt in to these cleaned checked-in texts via load_cleaned().
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

CORPUS_DIR = Path(__file__).resolve().parent / "corpora"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

START = re.compile(r"(?m)^\*{3}\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*\*{3}\s*$")
END = re.compile(r"(?m)^\*{3}\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*\*{3}\s*$")
FIRST = {
    766: re.compile(r"(?im)^CHAPTER 1\.\s+I AM BORN\s*$"),
    1342: re.compile(r"(?im)^Chapter 1\s*$"),
    84: re.compile(r"(?im)^Letter 1\s*$"),
    120: re.compile(r"(?im)^PART ONE--The Old Buccaneer\s*$"),
}
EXPECTED_CHAPTERS = {766: 64, 1342: 61, 84: 24, 120: 34}
EXPECTED_LETTERS = {766: 0, 1342: 0, 84: 4, 120: 0}


def git_blob_sha(data: bytes) -> str:
    return sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def clean_source(raw: str, ebook_id: int) -> tuple[str, dict]:
    """Remove Gutenberg paratext, not actual narrative grammar or punctuation."""
    if ebook_id not in FIRST:
        raise ValueError(f"Unsupported book: {ebook_id}")
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    start, end = START.search(raw), END.search(raw)
    if not start or not end or end.start() <= start.end():
        raise ValueError(f"Missing Gutenberg markers: {ebook_id}")
    body = raw[start.end():end.start()]
    first = FIRST[ebook_id].search(body)
    if not first:
        raise ValueError(f"Missing first narrative section: {ebook_id}")
    body = body[first.start():]
    paragraphs = [p.strip() for p in re.split(r"\n[ \t]*\n+", body) if p.strip()]
    clean = []
    removed = {}
    chapter_ids, letter_ids = [], []
    pending_title = False
    pending_letter_metadata = 0

    def skip(tag: str) -> None:
        removed[tag] = removed.get(tag, 0) + 1

    for paragraph in paragraphs:
        flat = re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", " ", paragraph)).strip()
        if re.match(r"^End of (?:the )?Project Gutenberg", flat, flags=re.I):
            skip("terminal_credit")
            break
        if ebook_id == 120 and re.fullmatch(r"\d{1,2}", flat):
            chapter_ids.append(int(flat))
            pending_title = True
            skip("chapter_number")
            continue
        if pending_title:
            pending_title = False
            skip("chapter_title")
            continue
        if ebook_id == 120 and re.match(r"^PART (?:ONE|TWO|THREE|FOUR|FIVE|SIX)--", flat):
            skip("part_title")
            continue
        if ebook_id == 766:
            match = re.match(r"^CHAPTER\s+(\d+)\.\s+\S+", flat, flags=re.I)
            if match:
                chapter_ids.append(int(match.group(1)))
                skip("chapter_heading")
                continue
        if ebook_id in (1342, 84):
            match = re.fullmatch(r"Chapter\s+(\d+)\s*", flat, flags=re.I)
            if match:
                chapter_ids.append(int(match.group(1)))
                skip("chapter_heading")
                continue
        if ebook_id == 84:
            match = re.fullmatch(r"Letter\s+(\d+)\s*", flat, flags=re.I)
            if match:
                letter_ids.append(int(match.group(1)))
                pending_letter_metadata = 2
                skip("letter_heading")
                continue
        if pending_letter_metadata:
            pending_letter_metadata -= 1
            skip("letter_metadata")
            continue
        if re.fullmatch(r"\*+(?:\s+\*+)+", flat):
            skip("decorative_separator")
            continue
        if flat.startswith("[") and flat.endswith("]"):
            skip("editorial_note")
            continue
        if ebook_id == 84 and re.fullmatch(
            r"(?:R\.?\s*W\.?|Your affectionate brother,\s*(?:R\. Walton|Robert Walton)?)",
            flat, flags=re.I,
        ):
            skip("letter_signature")
            continue
        normalized = flat.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
        normalized = re.sub(r"_([^_\n]+)_", r"\1", normalized)
        if normalized:
            clean.append(normalized)

    if chapter_ids != list(range(1, EXPECTED_CHAPTERS[ebook_id] + 1)):
        raise ValueError(f"Chapter sequence mismatch for {ebook_id}: {chapter_ids}")
    if letter_ids != list(range(1, EXPECTED_LETTERS[ebook_id] + 1)):
        raise ValueError(f"Letter sequence mismatch for {ebook_id}: {letter_ids}")
    result = "\n\n".join(clean) + "\n"
    if len(clean) < 500 or re.search(
        r"(?im)Project Gutenberg|^\s*(?:CONTENTS|PREFACE|CHAPTER \d+|Letter \d+|PART ONE)\b",
        result,
    ):
        raise ValueError(f"Text has leaked paratext or is unexpectedly short: {ebook_id}")
    return result, {"paragraphs": len(clean), "chapters": len(chapter_ids),
                    "letters": len(letter_ids), "removed": removed}


def load_cleaned(book) -> tuple[str, dict]:
    """Read and verify local corpus. Preserves download()'s metadata shape."""
    matches = [b for b in read_manifest()["books"] if b["ebook_id"] == book.ebook_id]
    if len(matches) != 1:
        raise KeyError(f"No cleaned corpus for ebook {book.ebook_id}")
    record = matches[0]
    path = CORPUS_DIR / Path(record["path"]).name
    raw = path.read_bytes()
    if git_blob_sha(raw) != record["clean_git_blob_sha"]:
        raise ValueError(f"Cleaned novel blob SHA mismatch: {path}")
    text = raw.decode("utf-8")
    if text.count("\n\n") + 1 != record["paragraphs"]:
        raise ValueError(f"Paragraph-count mismatch: {path}")
    return text, {
        "id": book.ebook_id, "title": record["title"],
        "author": record["author"], "role": book.role,
        "url": record["source_url"], "sha256": sha256(raw).hexdigest(),
        "raw_bytes": len(raw), "local_cleaned": True,
        "source_git_blob_sha": record["source_git_blob_sha"],
        "clean_git_blob_sha": record["clean_git_blob_sha"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Verify checked-in corpus hashes")
    action.add_argument("--rebuild", action="store_true", help="Rebuild only from matching pinned upstream bytes")
    args = parser.parse_args()
    for record in read_manifest()["books"]:
        path = CORPUS_DIR / Path(record["path"]).name
        if args.rebuild:
            request = Request(record["source_raw_url"], headers={"User-Agent": "Seman2-corpus-rebuild/1.0"})
            with urlopen(request, timeout=100) as response:
                raw = response.read()
            if git_blob_sha(raw) != record["source_git_blob_sha"]:
                raise RuntimeError(f"Upstream changed for ebook {record['ebook_id']}; refusing rebuild")
            text, counts = clean_source(raw.decode("utf-8-sig"), record["ebook_id"])
            cooked = text.encode("utf-8")
            if git_blob_sha(cooked) != record["clean_git_blob_sha"]:
                raise RuntimeError(f"Rebuild differs for ebook {record['ebook_id']}; refusing overwrite")
            if counts["paragraphs"] != record["paragraphs"]:
                raise RuntimeError("Regenerated paragraph count differs")
            path.write_bytes(cooked)
        data = path.read_bytes()
        if git_blob_sha(data) != record["clean_git_blob_sha"]:
            raise RuntimeError(f"Checked-in SHA mismatch: {path}")
        if data.decode("utf-8").count("\n\n") + 1 != record["paragraphs"]:
            raise RuntimeError(f"Paragraph count mismatch: {path}")
        print(f"OK {record['ebook_id']:4d} {record['title']}: "
              f"{record['paragraphs']} paragraphs, SHA {record['clean_git_blob_sha']}")


if __name__ == "__main__":
    main()
