"""Experimental independent SRL-BERT comparator, not production code."""
import argparse,json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen
from seman_parser.srl import project
from scripts.audit_srl import GOLD,evaluate
from scripts.review_srl import SPEECH_RETURN,UP_URL,UP_REV,parse_external,external_report

MODEL="https://storage.googleapis.com/allennlp-public-models/structured-prediction-srl-bert.2020.12.15.tar.gz"

def convert(text,native):
    # Convert documented BIO output to span records, preserving each frame.
    # This is serialization, not a linguistic inference.
    tokens=native["words"]; frames=[]
    for verb in native["verbs"]:
        tags=verb["tags"]
        if len(tags)!=len(tokens):raise ValueError("BIO cardinality mismatch")
        spans=[]; start=None; label=None
        for i,tag in enumerate(tags+["O"]):
            if tag.startswith("I-") and label==tag[2:]:continue
            if start is not None:
                spans.append([" ".join(tokens[start:i]),"PRED" if label=="V" else label,start,i])
                start=None; label=None
            if tag.startswith("B-"):
                start=i;label=tag[2:]
            elif tag!="O":raise ValueError("Malformed upstream BIO "+tag)
        frames.append(spans)
    return {**project(text,tokens,frames),"native_bio":native}

def main():
    p=argparse.ArgumentParser();p.add_argument("--out-dir",type=Path,required=True);args=p.parse_args()
    from allennlp.predictors.predictor import Predictor
    import allennlp_models.structured_prediction
    predictor=Predictor.from_path(MODEL,predictor_name="semantic_role_labeling",cuda_device=-1)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    counts=Counter()
    with (args.out_dir/"diagnostic.jsonl").open("w") as out:
        for c in json.loads(GOLD.read_text()):
            report=convert(c["text"],predictor.predict(c["text"]))
            checks=evaluate(c,report)
            counts["passages"]+=1;counts["targets"]+=len(checks)
            counts["exact"]+=sum(x["exact"] for x in checks)
            counts["predicate_found"]+=sum(x["predicate_found"] for x in checks)
            counts["unmapped"]+=report["alignment"]!="exact"
            if c["id"] not in SPEECH_RETURN:
                counts["pb_compatible_targets"]+=len(checks)
                counts["pb_compatible_exact"]+=sum(x["exact"] for x in checks)
            out.write(json.dumps({"case":c,"report":report,"checks":checks},ensure_ascii=False)+"\n");out.flush()
    with urlopen(UP_URL,timeout=60) as f:raw=f.read()
    cases,excluded,eligible=parse_external(raw)
    if len(cases)!=200:raise ValueError("Incomplete external sample")
    ext=Counter()
    with (args.out_dir/"external.jsonl").open("w") as out:
        for c in cases:
            report=convert(" ".join(c["tokens"]),predictor.predict_tokenized(c["tokens"]))
            if [x["text"] for x in report["tokens"]]!=c["tokens"]:raise ValueError("Token drift")
            row=external_report(c,report);ext.update(row);ext["sentences"]+=1
            out.write(json.dumps({**c,"report":report,"counts":dict(row)},ensure_ascii=False)+"\n");out.flush()
            if ext["sentences"]%40==0:print("ALLEN_SRL_PROGRESS",dict(ext),flush=True)
    summary={"model":MODEL,"diagnostic":dict(counts),"external":{"revision":UP_REV,
        "source_sha256":sha256(raw).hexdigest(),"eligible":eligible,"selection_exclusions":dict(excluded),"counts":dict(ext)},
        "limitations":"Native predictor uses spaCy VERB/AUX candidates, not joint end-to-end predicate detection. External metric is projected head recall."}
    (args.out_dir/"summary.json").write_text(json.dumps(summary,indent=2))
    print("ALLEN_SRL_FINAL",json.dumps(summary),flush=True)

if __name__=="__main__":main()
