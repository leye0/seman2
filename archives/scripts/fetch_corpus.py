#!/usr/bin/env python3
"""Retrieve the corpus locally.

Reddit and Stack Overflow are rebuilt as canonical Parquet files. Wikipedia is
kept as its original compressed XML dump for a dedicated streaming reader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts/build_canonical_parquet.py"
MANIFESTS = {
    "reddit": ROOT / "data/parquet/reddit/schema_version=1/manifest.json",
    "stackoverflow": ROOT
    / "data/parquet/stackoverflow/schema_version=1/manifest.json",
}
WIKIPEDIA_PATH = ROOT / "data/enwiki-latest-pages-articles-multistream.xml.bz2"
WIKIPEDIA_URL = (
    "https://dumps.wikimedia.org/enwiki/latest/"
    "enwiki-latest-pages-articles-multistream.xml.bz2"
)
WIKIPEDIA_SHA1_URL = (
    "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-sha1sums.txt"
)


def ensure_local_python() -> None:
    local_python = ROOT / ".venv/bin/python"
    if Path(sys.prefix).resolve() == (ROOT / ".venv").resolve():
        return
    if not local_python.is_file():
        raise SystemExit(
            "Environnement local absent. Exécuter d'abord: "
            "./scripts/seman2 install-tools"
        )
    os.execve(
        local_python,
        [str(local_python), str(Path(__file__).resolve()), *sys.argv[1:]],
        os.environ.copy(),
    )


ensure_local_python()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def wikipedia_sha1() -> str:
    filename = WIKIPEDIA_PATH.name
    dated_suffix = filename.removeprefix("enwiki-latest")
    request = urllib.request.Request(
        WIKIPEDIA_SHA1_URL,
        headers={"User-Agent": "seman2-corpus-fetcher/1.0"},
    )
    with urllib.request.urlopen(request) as response:
        checksums = response.read().decode("utf-8")
    for line in checksums.splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2:
            continue
        checksum, listed_filename = fields
        listed_filename = listed_filename.lstrip("* ")
        if listed_filename == filename or listed_filename.endswith(dated_suffix):
            return checksum
    raise RuntimeError(f"SHA-1 Wikipédia absent de {WIKIPEDIA_SHA1_URL}")


def process_wikipedia(verify_hashes: bool, dry_run: bool) -> tuple[int, int]:
    if WIKIPEDIA_PATH.is_file() and not verify_hashes:
        print("[wikipedia] dump XML Bzip2 déjà présent", flush=True)
        return 1, 0
    if dry_run:
        state = "déjà présent" if WIKIPEDIA_PATH.is_file() else "à télécharger"
        print(f"[wikipedia] dump XML Bzip2 {state}", flush=True)
        return (1, 0) if WIKIPEDIA_PATH.is_file() else (0, 1)

    expected_sha1 = wikipedia_sha1()
    if WIKIPEDIA_PATH.is_file():
        print("[wikipedia] vérification SHA-1 du dump", flush=True)
        if file_hash(WIKIPEDIA_PATH, "sha1") == expected_sha1:
            print("[wikipedia] dump XML Bzip2 valide", flush=True)
            return 1, 0
        WIKIPEDIA_PATH.unlink()

    print("[wikipedia] téléchargement du dump XML Bzip2", flush=True)
    download(WIKIPEDIA_URL, WIKIPEDIA_PATH)
    if file_hash(WIKIPEDIA_PATH, "sha1") != expected_sha1:
        raise RuntimeError("SHA-1 incorrect pour le dump Wikipédia")
    print("[wikipedia] dump XML Bzip2 téléchargé et validé", flush=True)
    return 0, 1


def source_url(dataset: str, source_file: str) -> str:
    if dataset == "reddit":
        prefix = "data/reddit-arctic-2018-05/"
        if not source_file.startswith(prefix):
            raise ValueError(f"Chemin Reddit inattendu: {source_file}")
        relative = source_file.removeprefix(prefix)
        return (
            "https://huggingface.co/datasets/open-index/arctic/resolve/main/"
            + relative
        )

    match = re.search(r"train-(\d{5})-of-00210-", source_file)
    if not match:
        raise ValueError(f"Chemin Stack Overflow inattendu: {source_file}")
    shard = int(match.group(1))
    return (
        "https://huggingface.co/datasets/"
        "suriyagunasekar/stackoverflow-with-meta-data/resolve/"
        f"refs%2Fconvert%2Fparquet/default/train/{shard:04d}.parquet"
    )


def expected_outputs(dataset: str, source_file: str, manifest: dict) -> list[dict]:
    source_path = Path(source_file)
    if dataset == "reddit":
        kind = source_path.parts[-4]
        output = (
            f"data/parquet/reddit/schema_version=1/{kind}/"
            f"part-{source_path.stem}.parquet"
        )
        paths = {output}
    else:
        match = re.search(r"train-(\d{5})-of-00210-", source_path.name)
        if not match:
            raise ValueError(f"Nom Stack Overflow inattendu: {source_path.name}")
        part = match.group(1)
        paths = {
            f"data/parquet/stackoverflow/schema_version=1/questions/part-{part}.parquet",
            f"data/parquet/stackoverflow/schema_version=1/answers/part-{part}.parquet",
        }
    outputs = [item for item in manifest["outputs"] if item["file"] in paths]
    if len(outputs) != len(paths):
        raise ValueError(f"Sorties absentes du manifeste pour {source_file}")
    return outputs


def outputs_are_valid(outputs: list[dict], verify_hashes: bool) -> bool:
    for item in outputs:
        path = ROOT / item["file"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            return False
        if verify_hashes and sha256(path) != item["sha256"]:
            return False
    return True


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    subprocess.run(
        [
            "curl",
            "-L",
            "--fail",
            "--retry",
            "5",
            "--retry-all-errors",
            "-C",
            "-",
            "-o",
            str(partial),
            url,
        ],
        check=True,
    )
    os.replace(partial, destination)


def rebuild_source(
    dataset: str,
    source: dict,
    outputs: list[dict],
) -> None:
    source_path = ROOT / source["file"]
    source_is_valid = (
        source_path.is_file()
        and source_path.stat().st_size == source["bytes"]
        and sha256(source_path) == source["sha256"]
    )
    if source_is_valid:
        print(f"\n[{dataset}] source locale reprise: {source_path.name}", flush=True)
    else:
        if source_path.exists():
            source_path.unlink()
        print(f"\n[{dataset}] téléchargement: {source_path.name}", flush=True)
        download(source_url(dataset, source["file"]), source_path)
        if source_path.stat().st_size != source["bytes"]:
            raise RuntimeError(f"Taille source incorrecte: {source_path}")
        if sha256(source_path) != source["sha256"]:
            raise RuntimeError(f"SHA-256 source incorrect: {source_path}")

    subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            str(BUILD_SCRIPT),
            "--dataset",
            dataset,
            "--force",
            "--no-manifest",
        ],
        cwd=ROOT,
        check=True,
    )
    if not outputs_are_valid(outputs, verify_hashes=True):
        raise RuntimeError(f"Sortie canonique non reproductible pour {source_path}")
    source_path.unlink()


def process_dataset(
    dataset: str,
    verify_hashes: bool,
    dry_run: bool,
) -> tuple[int, int]:
    manifest_path = MANIFESTS[dataset]
    if not manifest_path.is_file():
        raise SystemExit(f"Manifeste versionné absent: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    complete = 0
    rebuilt = 0
    for index, source in enumerate(manifest["sources"], start=1):
        outputs = expected_outputs(dataset, source["file"], manifest)
        source_path = ROOT / source["file"]
        if outputs_are_valid(outputs, verify_hashes):
            complete += 1
            if source_path.exists() and not dry_run:
                source_path.unlink()
            print(
                f"[{dataset} {index}/{len(manifest['sources'])}] déjà présent",
                flush=True,
            )
            continue
        rebuilt += 1
        if dry_run:
            print(
                f"[{dataset} {index}/{len(manifest['sources'])}] à reconstruire",
                flush=True,
            )
            continue
        rebuild_source(dataset, source, outputs)
    return complete, rebuilt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Récupère uniquement le corpus Parquet canonique final."
    )
    parser.add_argument(
        "--dataset",
        choices=("all", "reddit", "stackoverflow", "wikipedia"),
        default="all",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="recalculer aussi le SHA-256 des sorties déjà présentes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="afficher le travail requis sans télécharger",
    )
    args = parser.parse_args()

    parquet_datasets = (
        ("reddit", "stackoverflow")
        if args.dataset == "all"
        else ((args.dataset,) if args.dataset != "wikipedia" else ())
    )
    total_complete = 0
    total_rebuilt = 0
    for dataset in parquet_datasets:
        complete, rebuilt = process_dataset(dataset, args.verify, args.dry_run)
        total_complete += complete
        total_rebuilt += rebuilt
    if args.dataset in ("all", "wikipedia"):
        complete, rebuilt = process_wikipedia(args.verify, args.dry_run)
        total_complete += complete
        total_rebuilt += rebuilt

    verb = "seraient reconstruits" if args.dry_run else "reconstruits"
    print(
        f"\nCorpus: {total_complete} fragments déjà complets, "
        f"{total_rebuilt} {verb}.",
        flush=True,
    )
    if not args.dry_run:
        print(
            "Reddit et Stack Overflow sont conservés en Parquet; "
            "Wikipédia reste en XML Bzip2.",
            flush=True,
        )


if __name__ == "__main__":
    main()
