"""Freeze a 2,000-unit discovery campaign from exact, versioned sources."""
import argparse,json
from collections import Counter
from hashlib import sha256,sha1
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree as ET
from scripts.novel_sources import EXPECTED_MANIFEST,pinned_novel_sources
from research.verbnet_lr.clean_novel_corpus import load_cleaned,read_manifest
from research.verbnet_lr.gutenberg_novels import TRAIN_BOOKS,extract
from research.verbnet_lr.corpus_pipeline import prepare_corpus_input

UP_REV="b955f2aa8295834fcd0256c131de641116a8443a"
UP_URL=f"https://raw.githubusercontent.com/UniversalPropositions/UP-1.0/{UP_REV}/UP_English-EWT/en_ewt-up-test.conllu"
UP_SHA="f511b4b39cf9525945fbb89660757b401d339d2deee805a36c3b4fc9ea2cd8b7"
WSD_REV="74ff055519b3c426330df9974a6603a0e638a3db"
WSD_ROOT=f"https://raw.githubusercontent.com/SapienzaNLP/wsd-hard-benchmark/{WSD_REV}/wsd_hard_benchmark/ALLamended/"
SIZES={"novel":1000,"contemporary":400,"complex":250,"wsd":200,"dialogue":150}
def digest(s):return sha256(s.encode()).hexdigest()
def order(tag,items):
    return sorted(items,key=lambda x:digest(tag+":"+x["id"]))
def read_jsonl(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l]
def write_jsonl(path,rows):
    with path.open("w") as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,default=str)+"\n")
def fetch(url,sha,*,git=False):
    with urlopen(url,timeout=90) as f:raw=f.read()
    actual=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest() if git else sha256(raw).hexdigest()
    if actual!=sha:raise ValueError("Source integrity mismatch: "+url)
    return raw
def record(cid,cohort,text,**extra):
    if not text.strip() or "\n" in text or "\r" in text:raise ValueError("Invalid source unit "+cid)
    return {"id":cid,"cohort":cohort,"text":text,"source_sha256":digest(text),**extra}

def up_pool(raw):
    """Exact existing eligibility; retain original # text and projected head gold."""
    pool=[]
    for block in raw.decode("utf-8").strip().split("\n\n"):
        lines=block.splitlines()
        if any(x.startswith("# propbank") for x in lines):continue
        ids=[x.split(" = ",1)[1] for x in lines if x.startswith("# sent_id = ")]
        texts=[x.split(" = ",1)[1] for x in lines if x.startswith("# text = ")]
        rows=[x.split("\t") for x in lines if x and not x.startswith("#")]
        if len(ids)!=1 or not rows or any(not x[0].isdigit() or len(x)<11 for x in rows):continue
        if not 5<=len(rows)<=35:continue
        preds=[i for i,x in enumerate(rows) if x[10]!="_"]
        if not preds or any(len(x)!=11+len(preds) for x in rows):continue
        targets=[]
        for j,i in enumerate(preds):
            if rows[i][3]!="VERB" or rows[i][11+j]!="V":continue
            for k,x in enumerate(rows):
                if x[11+j].startswith(("ARG","R-ARG","C-ARG")):targets.append([i,x[11+j],k])
        if not targets:continue
        tokens=[x[1] for x in rows]
        pool.append({"id":ids[0],"tokens":tokens,"targets":targets,"original_text":texts[0] if len(texts)==1 else None,
            "rolesets":[[i,rows[i][10]] for i in preds],"ud_rows":[x[:10] for x in rows],
            "clausal_edges":sum(x[7].split(":")[0] in {"acl","advcl","ccomp","xcomp","conj","parataxis"} for x in rows)})
    return pool

def select_up(raw,seen):
    pool=up_pool(raw)
    if len(pool)!=1088:raise ValueError("External eligibility drift")
    previous={x["id"] for x in order("up-srl-v1",pool)[:200]}
    eligible=[x for x in pool if x["id"] not in previous and x["original_text"] and digest(x["original_text"]) not in seen]
    # Research sampling only: native gold dependency metadata, never production rules.
    complex_pool=[x for x in eligible if x["clausal_edges"]>=1 or len({t[0] for t in x["targets"]})>=2]
    selected=[]
    for cohort,n,items in [("complex",250,complex_pool),("contemporary",400,eligible)]:
        added=0
        for x in order("campaign-v1-"+cohort,items):
            text=x["original_text"];key=digest(text)
            if key in seen:continue
            seen.add(key)
            selected.append(record("UP:"+x["id"],cohort,text,external=x))
            added+=1
            if added==n:break
        if added!=n:raise ValueError("Not enough distinct "+cohort+" cases")
    return selected

def select_wsd(xml,keys,seen):
    gold={}
    for line in keys.decode().splitlines():
        if line.strip():
            k,*v=line.split();gold[k]=v
    pool=[]
    for sent in ET.fromstring(xml).iter("sentence"):
        parts=[];targets=[];cursor=0
        for node in sent:
            value=node.text or ""
            if not value:continue
            if parts:cursor+=1
            a=cursor;cursor+=len(value);parts.append(value)
            if node.tag=="instance" and node.get("id") in gold and node.get("pos") in {"NOUN","VERB","ADJ","ADV"}:
                targets.append({"id":node.get("id"),"span":[a,cursor],"lemma":node.get("lemma"),
                    "pos":node.get("pos"),"gold_keys":gold[node.get("id")],"text":value})
        text=" ".join(parts)
        if not 5<=len(parts)<=35 or not targets or "\n" in text or "\r" in text:continue
        # One target per sentence, frozen independent of predictions.
        target=order("campaign-v1-wsd-target",targets)[0]
        pool.append(record("WSD:"+sent.get("id"),"wsd",text,wsd_target=target,
            representation="publisher XML tokens joined by single spaces"))
    selected=[]
    for c in order("campaign-v1-wsd",pool):
        if c["source_sha256"] in seen:continue
        seen.add(c["source_sha256"]);selected.append(c)
        if len(selected)==200:break
    if len(selected)!=200:raise ValueError("Insufficient WSD cases")
    return selected

def build(native_dir):
    summary=json.loads((native_dir/"summary.json").read_text())
    if summary["manifest_sha256"]!=EXPECTED_MANIFEST or summary["evaluated_cases"]!=1000 or not summary["complete_corpus"]:
        raise ValueError("Wrong native baseline")
    if summary["grammar_sha256"]!="2968621bf88d50cffa9ec52c5edead7b16aabff573421f2f97c113e056ff5c82" or summary["ace_sha256"]!="4e3726a9e017d1e3eaa99fb89b873dfeaac3c0c0bd1989927cef6c42421f57ca":
        raise ValueError("Native version mismatch")
    native=read_jsonl(native_dir/"cases.jsonl")
    if [x["case_id"] for x in native]!=[f"Q3-{i}" for i in range(1,1001)]:raise ValueError("Native source IDs drift")
    manifest,cases=pinned_novel_sources()
    rows=[];seen=set();spans={}
    for (cid,c),prior in zip(cases,native):
        prep=prepare_corpus_input(c)
        if prep.analysis_text!=prior["source_text"] or prior["whole"]["source_text"]!=prior["source_text"]:raise ValueError("Native source mismatch "+cid)
        key=digest(prep.analysis_text)
        seen.add(key)
        spans.setdefault(c["book_id"],[]).append(c["structural_core_source_span"])
        rows.append(record(cid,"novel",prep.analysis_text,book_id=c["book_id"],book_span=c["structural_core_source_span"],
            constituents=list(prep.structural_constituents)))
    # Select new, non-overlapping dialogue spans from the same verified editions.
    books={b.ebook_id:b for b in TRAIN_BOOKS}
    pool=[]
    for edition in read_manifest()["books"]:
        bid=edition["ebook_id"];book=books[bid];body,info=load_cleaned(book)
        eligible,_=extract(book,body,length_min=4,length_max=32)
        for c in eligible:
            a,b=c["structural_core_source_span"]
            if any(max(a,x)<min(b,y) for x,y in spans.get(bid,[])):continue
            if not any(p["function"]=="spoken_clause_candidate" for p in c["structural_constituents"]):continue
            prep=prepare_corpus_input(c)
            if " ".join(body[a:b].split())!=prep.analysis_text:raise ValueError("New dialogue source mismatch")
            pool.append(record(f"DLG:{bid}:{a}:{b}","dialogue",prep.analysis_text,book_id=bid,book_span=[a,b],
                book_sha256=info["sha256"],constituents=list(prep.structural_constituents)))
    dialogues=[]
    for c in order("campaign-v1-dialogue",pool):
        if c["source_sha256"] in seen:continue
        a,b=c["book_span"];bid=c["book_id"]
        if any(max(a,x)<min(b,y) for x,y in spans.get(bid,[])):continue
        spans.setdefault(bid,[]).append([a,b]);seen.add(c["source_sha256"]);dialogues.append(c)
        if len(dialogues)==150:break
    rows.extend(dialogues)
    rows.extend(select_up(fetch(UP_URL,UP_SHA),seen))
    rows.extend(select_wsd(fetch(WSD_ROOT+"ALLamended.data.xml","39fd90273022aacfd35f69bea9aae313a9dbcd9e",git=True),
        fetch(WSD_ROOT+"ALLamended.gold.key.txt","de5bbff78a903817b67291ee1cbdfa7048d24231",git=True),seen))
    counts=Counter(x["cohort"] for x in rows)
    if dict(counts)!=SIZES or len({x["id"] for x in rows})!=2000:raise ValueError("Campaign cardinality mismatch "+repr(counts))
    # Historical novel IDs remain intact, even if there are repeat surface strings.
    return rows,{"schema":"gap-campaign-v1","counts":dict(counts),"unique_texts":len({x["source_sha256"] for x in rows}),
        "novel_manifest":manifest,"up_revision":UP_REV,"up_sha256":UP_SHA,"wsd_revision":WSD_REV,
        "manifest_sha256":digest(json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(",",":"))),
        "native_baseline_run":46152217691,"sampling":"No predictions consulted for new cohort selection."}

def load_campaign(directory):
    rows=read_jsonl(directory/"cases.jsonl");m=json.loads((directory/"manifest.json").read_text())
    if len(rows)!=2000 or Counter(x["cohort"] for x in rows)!=SIZES or len({x["id"] for x in rows})!=2000:
        raise ValueError("Campaign cardinality drift")
    if digest(json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(",",":")))!=m["manifest_sha256"]:
        raise ValueError("Campaign manifest drift")
    if any(digest(x["text"])!=x["source_sha256"] for x in rows):raise ValueError("Source hash drift")
    return rows,m

def main():
    p=argparse.ArgumentParser();p.add_argument("--native",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    rows,m=build(a.native);write_jsonl(a.out/"cases.jsonl",rows)
    (a.out/"manifest.json").write_text(json.dumps(m,indent=2))
    print("CAMPAIGN_MANIFEST",json.dumps(m),flush=True)
if __name__=="__main__":main()
