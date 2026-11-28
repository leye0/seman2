"""Measure marginal inventory coverage and cost using actual WSD artifact."""
import argparse,json,tracemalloc
from collections import Counter
from pathlib import Path
from time import perf_counter
from seman_parser.role_resources import RoleResources,manifest

def main():
    p=argparse.ArgumentParser();p.add_argument("--data",type=Path,required=True);p.add_argument("--wsd",type=Path,required=True);p.add_argument("--out",type=Path,required=True);args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    wsd_summary=json.loads((args.wsd/"summary.json").read_text())
    if wsd_summary["provider"]["wordnet"]!="3.0":raise ValueError("WordNet version mismatch")
    tracemalloc.start();start=perf_counter()
    resources=RoleResources(args.data)
    load_ms=(perf_counter()-start)*1000
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    counts=Counter();records=[];duration=0
    for line in (args.wsd/"cases.jsonl").read_text().splitlines():
        c=json.loads(line); t=c["wsd"]; pred=t["prediction"]
        if not pred or pred["pos"]!="v":continue
        start=perf_counter()
        inv=resources.wordnet(pred["offset"],pred["pos"])
        alt=[{"id":s["id"],"inventory":resources.wordnet(s["offset"],s["pos"])}
             for s in t["alternatives"] if s["pos"]=="v"]
        duration+=(perf_counter()-start)
        counts["verbal_targets"]+=1;counts["mapped_top1"]+=bool(inv["matches"])
        counts["has_role_structure_top1"]+=any(m["role_structure_rows"] for m in inv["matches"])
        counts["any_sense_mapped"]+=any(x["inventory"]["matches"] for x in alt)
        counts["alternative_senses"]+=len(alt)
        counts["mapped_alternatives"]+=sum(bool(x["inventory"]["matches"]) for x in alt)
        record={"id":c["id"],"text":c["text"],"prediction":pred,"inventory":inv,"alternatives":alt}
        records.append(record)
        print("ROLE_CASE",json.dumps({"id":c["id"],"sense":pred["id"],"frames":[{"id":m["frame_id"],"info":m["frame_info_rows"],"roles":m["role_structure_rows"]} for m in inv["matches"]]},ensure_ascii=False),flush=True)
    # Independent exhaustive inventory check, not inference accuracy.
    total=len(resources.wn);mapped=sum(any(resources.bn.get(r[0]) for r in rs) for rs in resources.wn.values())
    report={"bytes":sum(r["bytes"] for r in manifest()),"initialization_ms_with_tracemalloc":load_ms,
        "python_peak_bytes":peak,"lookup_ms_total":duration*1000,"diagnostics":dict(counts),
        "inventory":{"wordnet_keys":total,"mapped_keys":mapped,"frame_keys":len(resources.pas),
                     "pb_va_rolesets":len(resources.pb_va),"pb_vn_rolesets":len(resources.pb_vn),"vn_fn_members":len(resources.vn_fn)},
        "limitations":"Inventory coverage only, not corrected SRL arguments. No extra neural inference."}
    (args.out/"cases.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records))
    (args.out/"summary.json").write_text(json.dumps(report,indent=2))
    print("ROLE_RESOURCES_FINAL",json.dumps(report),flush=True)
if __name__=="__main__":main()
