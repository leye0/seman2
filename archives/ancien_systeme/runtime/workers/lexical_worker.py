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
from nltk.corpus import framenet, propbank, verbnet, wordnet
from nltk.stem import WordNetLemmatizer


root = Path(request["root"])
candidate_limit = int(request["max_lexical_candidates"])
semlink_root = root / ".local/share/semlink"
sumo_mapping_root = root / ".local/share/sumo/WordNetMappings"
try:
    pb_vn = json.loads((semlink_root / "instances/pb-vn2.json").read_text())
    vn_fn = json.loads((semlink_root / "instances/vn-fn2.json").read_text())
    semlink_available = True
except (OSError, json.JSONDecodeError):
    pb_vn = {}
    vn_fn = {}
    semlink_available = False

SUMO_FILES = {
    "n": "WordNetMappings30-noun.txt",
    "v": "WordNetMappings30-verb.txt",
    "a": "WordNetMappings30-adj.txt",
    "r": "WordNetMappings30-adv.txt",
}
SUMO_PATTERN = re.compile(r"&%([^\s&]+?)([=+@:\[\]])(?=\s|$)")
SUMO_RELATIONS = {
    "=": "equivalent_to",
    "+": "subsumed_by",
    "@": "instance_of",
    ":": "not_equivalent_to",
    "[": "not_subsumed_by",
    "]": "not_instance_of",
}

forms = []
seen = set()
for match in re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", request["text"]):
    form = match.group(0).casefold()
    if form not in seen:
        seen.add(form)
        forms.append({"form": form, "charspan": list(match.span())})
    if len(forms) >= int(request["max_lexical_forms"]):
        break
lemmatizer = WordNetLemmatizer()
results = []
for occurrence in forms:
    form = occurrence["form"]
    lemmas = sorted(
        {
            lemmatizer.lemmatize(form, pos)
            for pos in ("n", "v", "a", "r")
        }
    )
    synsets = wordnet.synsets(form)[:candidate_limit]
    vn = sorted(
        {
            class_id
            for lemma in lemmas
            for class_id in verbnet.classids(lemma)
        }
    )[:candidate_limit]
    pb = []
    pb_details = []
    for lemma in lemmas:
        for sense in range(1, candidate_limit + 1):
            identifier = f"{lemma}.{sense:02d}"
            try:
                roleset = propbank.roleset(identifier)
            except Exception:
                continue
            pb.append(identifier)
            pb_details.append(
                {
                    "roleset_id": identifier,
                    "name": roleset.get("name"),
                    "roles": [
                        {
                            "argument": f"ARG{role.get('n')}",
                            "function": role.get("f"),
                            "description": role.get("descr"),
                        }
                        for role in roleset.findall("roles/role")
                    ],
                }
            )
    frame_rows = []
    for lemma in lemmas:
        try:
            lexical_units = framenet.lus(
                r"(?i)^" + re.escape(lemma) + r"\."
            )[:candidate_limit]
        except Exception:
            lexical_units = []
        for lexical_unit in lexical_units:
            record = {
                "lexical_unit_id": lexical_unit.ID,
                "lexical_unit": lexical_unit.name,
                "frame_id": lexical_unit.frame.ID,
                "frame": lexical_unit.frame.name,
            }
            if record not in frame_rows:
                frame_rows.append(record)
    semlink_rows = []
    for roleset_id in pb:
        for numeric_class, role_mapping in pb_vn.get(roleset_id, {}).items():
            frame_names = sorted(
                {
                    frame
                    for key, frames in vn_fn.items()
                    if key.startswith(numeric_class + "-")
                    for frame in frames
                }
            )[:candidate_limit]
            semlink_rows.append(
                {
                    "propbank_roleset": roleset_id,
                    "verbnet_class": numeric_class,
                    "role_mapping": role_mapping,
                    "framenet_frames": frame_names,
                }
            )
    results.append(
        {
            **occurrence,
            "lemmas": lemmas,
            "wordnet": [
                {
                    "synset": row.name(),
                    "pos": row.pos(),
                    "definition": row.definition(),
                    "lemmas": sorted(row.lemma_names()),
                    "offset": row.offset(),
                    "hypernyms": sorted(item.name() for item in row.hypernyms())[
                        :candidate_limit
                    ],
                }
                for row in synsets
            ],
            "verbnet_class_ids": vn,
            "verbnet_classes": [
                {
                    "class_id": class_id,
                    "thematic_roles": [
                        role["type"] for role in verbnet.themroles(class_id)
                    ],
                    "frame_count": len(verbnet.frames(class_id)),
                }
                for class_id in vn
            ],
            "propbank_roleset_ids": pb,
            "propbank_rolesets": pb_details,
            "framenet_candidates": frame_rows[:candidate_limit],
            "semlink_mappings": semlink_rows[:candidate_limit],
        }
    )

target_synsets = {
    ((synset.pos() if synset.pos() != "s" else "a"), synset.offset())
    for occurrence in results
    for synset in wordnet.synsets(occurrence["form"])[:candidate_limit]
}
sumo_by_synset = {key: [] for key in target_synsets}
for pos, filename in SUMO_FILES.items():
    wanted = {offset for key_pos, offset in target_synsets if key_pos == pos}
    if not wanted:
        continue
    try:
        with (sumo_mapping_root / filename).open(
            encoding="utf-8", errors="replace"
        ) as handle:
            for line_number, line in enumerate(handle, start=1):
                if len(line) < 9 or not line[:8].isdigit():
                    continue
                offset = int(line[:8])
                if offset not in wanted:
                    continue
                payload = line.split("|", 1)[1] if "|" in line else ""
                sumo_by_synset[(pos, offset)] = [
                    {
                        "concept": concept,
                        "operator": operator,
                        "relation": SUMO_RELATIONS[operator],
                        "source_file": filename,
                        "source_line": line_number,
                    }
                    for concept, operator in SUMO_PATTERN.findall(payload)
                ][:candidate_limit]
    except OSError:
        continue
for occurrence in results:
    for synset in occurrence["wordnet"]:
        pos = "a" if synset["pos"] == "s" else synset["pos"]
        synset["sumo_mappings"] = sumo_by_synset.get((pos, synset["offset"]), [])
json.dump(
    {
        "status": "analyzed",
        "occurrence_count": len(results),
        "occurrences": results,
        "providers": {
            "wordnet": "queried",
            "verbnet": "queried",
            "propbank": "queried",
            "framenet": "queried",
            "semlink": "queried" if semlink_available else "resource-unavailable",
            "sumo": "queried" if sumo_mapping_root.is_dir() else "resource-unavailable",
        },
    },
    sys.stdout,
    ensure_ascii=False,
)
sys.stdout.write("\n")
