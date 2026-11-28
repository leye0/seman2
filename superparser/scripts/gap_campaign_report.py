"""Paired failure census, provenance, and marginal cost; research-only."""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from scripts.gap_campaign_sources import load_campaign,read_jsonl,write_jsonl

def main():
    p=argparse.ArgumentParser();p.add_argument("--campaign",type=Path,required=True);p.add_argument("--results",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    cases,m=load_campaign(a.campaign);a.out.mkdir(parents=True,exist_ok=True)
    models={};cost={}
    for mode in ("erg","hanlp","allen","lexical"):
        d=a.results/("gap-"+mode)
        s=json.loads((d/"summary.json").read_text())
        if s["manifest_sha256"]!=m["manifest_sha256"] or s["mode"]!=mode:raise ValueError("Provider manifest mismatch")
        rows=read_jsonl(d/"observations.jsonl");models[mode]={x["id"]:x for x in rows}
        expected={c["id"] for c in cases if mode!="allen" or "external" in c}
        if set(models[mode])!=expected or len(rows)!=len(expected):raise ValueError("Provider cardinality "+mode)
        cost[mode]={**s,"artifact_bytes":sum(f.stat().st_size for f in d.rglob("*") if f.is_file())}
    counters=defaultdict(Counter);families=defaultdict(Counter);gaps=[]
    for c in cases:
        cid=c["id"];co=c["cohort"];count=counters[co];count["cases"]+=1
        obs={mode:r[cid] for mode,r in models.items() if cid in r}
        if any(x["source_sha256"]!=c["source_sha256"] for x in obs.values()):raise ValueError("Provider source mismatch "+cid)
        def gap(kind,**details):gaps.append({"id":cid,"cohort":co,"kind":kind,**details});count[kind]+=1
        e=obs["erg"];h=obs["hanlp"];l=obs["lexical"]
        if e["status"]!="has_native_analysis":gap("erg_no_native_analysis",status=e["status"])
        if e["all_flagged"]:gap("erg_all_readings_flagged")
        if e["at_cap"]:gap("erg_result_cap")
        if not h["report"]["frames"]:gap("hanlp_no_frames",classification="coverage_only")
        if h["report"]["alignment"]!="exact":gap("hanlp_unmapped_tokens",classification="interface")
        for t in l["tokens"]:
            count["lexical_tokens"]+=1
            if not t["senses"]:gap("wordnet_no_candidate",token=t,classification="inventory_only")
            if t["pos"]=="v" and t["senses"] and not t["verbatlas_mapped"]:gap("verbatlas_no_mapping",token=t,classification="inventory_only")
        if l["wsd"] is not None:
            w=l["wsd"];count["wsd_targets"]+=1;count["wsd_hits"]+=w["hit"];count["wsd_first_sense_hits"]+=w["first_sense_hit"]
            if not w["hit"]:gap("wsd_gold_miss",target=w["target"],prediction=w["prediction"]["prediction"],
                gold_in_inventory=w["gold_in_inventory"],classification="gold")
        if "allen" in obs:
            ac=obs["allen"]["checks"];hc=h["checks"]
            if len(ac)!=len(hc) or [x["target"] for x in ac]!=[x["target"] for x in hc]:raise ValueError("Paired gold drift")
            for x,y in zip(hc,ac):
                label=x["target"][1];family=families[label];count["srl_targets"]+=1
                k="both" if x["hit"] and y["hit"] else "hanlp_only" if x["hit"] else "allen_only" if y["hit"] else "neither"
                for bucket in (count,family):bucket[k]+=1;bucket["hanlp_hits"]+=x["hit"];bucket["allen_hits"]+=y["hit"];bucket["targets"]+=1
                if not x["hit"] or not y["hit"]:
                    gap("srl_"+k,target=x["target"],hanlp_predicate_found=x["predicate_found"],allen_predicate_found=y["predicate_found"],classification="gold_projected_head")
    report={"manifest":m,"by_cohort":{k:dict(v) for k,v in counters.items()},"srl_by_role":{k:dict(v) for k,v in families.items()},
        "cost":cost,"gap_records":len(gaps),"limitations":["No gold SRL on literary or WSD-only cases; coverage signals are not errors.",
        "External head recall not span F1 or precision; oracle complementarity not automatic selection.",
        "CPU runner wall time and peak process RSS include runtime overhead; artifact bytes not deployed model size.",
        "WSD supplied gold lemma/POS; training overlap not established. No production edits or automatic lexical repairs."]}
    write_jsonl(a.out/"gaps.jsonl",gaps);(a.out/"summary.json").write_text(json.dumps(report,indent=2))
    print("CAMPAIGN_FINAL",json.dumps(report),flush=True)
if __name__=="__main__":main()
