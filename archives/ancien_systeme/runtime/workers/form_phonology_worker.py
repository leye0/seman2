#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import re
import resource
import sys

request = json.load(sys.stdin)
limit = int(request["memory_limit_mib"]) * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
import epitran
import panphon

forms = []
seen = set()
for match in re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", request["text"]):
    form = match.group(0).casefold()
    if form not in seen:
        seen.add(form)
        forms.append({"form": form, "charspan": list(match.span())})
    if len(forms) >= int(request["max_form_occurrences"]):
        break
targets = {row["form"] for row in forms}
cmu_candidates = {form: [] for form in targets}
cmu_path = Path(request["root"]) / ".local/share/nltk_data/corpora/cmudict/cmudict"
try:
    with cmu_path.open(encoding="latin-1") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 3:
                continue
            word = re.sub(r"\(\d+\)$", "", parts[0].casefold())
            if word in targets and parts[2:] not in cmu_candidates[word]:
                cmu_candidates[word].append(parts[2:])
except OSError:
    pass
rows = []
errors = []
try:
    transcriber = epitran.Epitran("eng-Latn")
except Exception as exc:
    transcriber = None
    errors.append(f"epitran-init:{type(exc).__name__}:{exc}")
feature_table = panphon.FeatureTable()
for occurrence in forms:
    ipa = None
    features = []
    if transcriber is not None:
        try:
            ipa = transcriber.transliterate(occurrence["form"])
            features = [segment.strings() for segment in feature_table.word_fts(ipa)]
        except Exception as exc:
            errors.append(f"{occurrence['form']}:{type(exc).__name__}:{exc}")
    rows.append(
        {
            **occurrence,
            "ipa": ipa,
            "panphon_features": features,
            "g2p_candidates": cmu_candidates[occurrence["form"]],
        }
    )
json.dump(
    {
        "status": "analyzed" if any(row["ipa"] for row in rows) else "failure",
        "occurrence_count": len(rows),
        "occurrences": rows,
        "errors": errors,
        "providers": {
            "epitran": "queried" if transcriber is not None else "failure",
            "panphon": "queried",
            "cmudict": "queried" if cmu_path.is_file() else "resource-unavailable",
            "phonetisaurus": "qualified-fallback-not-invoked-for-known-forms",
        },
        "native_values_preserved": True,
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
