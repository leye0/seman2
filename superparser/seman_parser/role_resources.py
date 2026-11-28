"""Local, versioned external role inventories. No model or inferred role filling."""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha1, sha256
import json
from pathlib import Path
from functools import lru_cache

MANIFEST=Path(__file__).with_name("role_resources_manifest.json")

def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))

def verify(raw,record):
    digest=sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if len(raw)!=record["bytes"] or digest!=record["git_blob_sha1"]:
        raise ValueError("Role resource integrity mismatch: "+record["name"])

def rows(raw):
    # Publisher's first line is the license/version header; retain all fields.
    return [line.split("\t") for line in raw.decode("utf-8").splitlines()[1:] if line.strip()]

def index(table, key=0):
    out=defaultdict(list)
    for row in table:
        out[row[key]].append(row)
    return dict(out)

class RoleResources:
    """Explicit local directory; no automatic network or model initialization."""
    def __init__(self,directory):
        data={}
        self.provenance=[]
        for rec in manifest():
            raw=(Path(directory)/rec["name"]).read_bytes()
            verify(raw,rec)
            self.provenance.append({**rec,"sha256":sha256(raw).hexdigest(),
                "header":raw.decode("utf-8").splitlines()[0] if rec["name"].endswith(".tsv") else None})
            data[rec["name"]]=json.loads(raw) if rec["name"].endswith(".json") else rows(raw)
        self.wn=index(data["bn2wn.tsv"],1)
        self.bn=index(data["VA_bn2va.tsv"])
        self.info=index(data["VA_frame_info.tsv"])
        self.pas=index(data["VA_frame_pas.tsv"])
        self.implicit=index(data["VA_bn2implicit.tsv"])
        self.shadow=index(data["VA_bn2shadow.tsv"])
        self.preferences=index(data["VA_va2sp.tsv"])
        self.preference_info=index(data["VA_preference_info.tsv"])
        self.pb_va=defaultdict(list)
        for row in data["pb2va.tsv"]:
            pb,va=row[0].split(">",1)
            self.pb_va[pb].append(row)
        self.pb_vn=data["pb-vn2.json"]
        self.vn_fn=data["vn-fn2.json"]

    @lru_cache(maxsize=8192)
    def wordnet(self,offset,pos):
        if not isinstance(offset,int) or not 0<=offset<=99999999 or pos!="v":
            raise ValueError("Expected WordNet 3.0 verbal synset offset")
        wn=f"wn:{offset:08d}{pos}"
        matches=[]
        for bnrow in self.wn.get(wn,[]):
            bn=bnrow[0]
            for row in self.bn.get(bn,[]):
                fid=row[1]
                prefs=self.preferences.get(fid,[])
                pref_ids={p for r in prefs for c in r[3::2] for p in c.split("|")}
                matches.append({"babelnet_mapping":bnrow,"synset_frame_mapping":row,
                    "frame_id":fid,"frame_info_rows":self.info.get(fid,[]),
                    "role_structure_rows":self.pas.get(fid,[]),
                    "selectional_preference_rows":prefs,
                    "preference_definition_rows":[v for p in sorted(pref_ids) for v in self.preference_info.get(p,[])],
                    "implicit_argument_rows":self.implicit.get(bn,[]),
                    "shadow_default_argument_rows":self.shadow.get(bn,[])})
        return {"wordnet_id":wn,"matches":matches,"status":"mapped" if matches else "unmapped"}

    @lru_cache(maxsize=8192)
    def propbank(self,roleset):
        """Exact publisher IDs; never infer a roleset from a bare lemma."""
        return {"roleset":roleset,"verbatlas_mapping_rows":self.pb_va.get(roleset,[]),
                "semlink_verbnet":self.pb_vn.get(roleset,{})}

    @lru_cache(maxsize=8192)
    def verbnet(self,member_id):
        """SemLink native key, e.g. 26.5-shake. No fuzzy class matching."""
        return {"member_id":member_id,"semlink_framenet":self.vn_fn.get(member_id,[])}

    def inspect_wsd(self,wsd):
        if wsd.get("provider",{}).get("wordnet")!="3.0":
            raise ValueError("Role mappings require WordNet 3.0 provenance")
        result=[]
        text=wsd["source_text"]
        if sha256(text.encode()).hexdigest()!=wsd["source_sha256"]:
            raise ValueError("WSD source digest mismatch")
        for t in wsd["targets"]:
            a,b=t["span"]
            if not 0<=a<b<=len(text) or text[a:b]!=t["text"]:
                raise ValueError("WSD target offset mismatch")
            alternatives=[{"sense":s,"inventory":self.wordnet(s["offset"],s["pos"])}
                          for s in t["alternatives"] if s["pos"]=="v"]
            if t["pos"]=="v" or alternatives:
                result.append({"span":t["span"],"text":t["text"],"lemma":t["lemma"],
                    "wsd_prediction":t["prediction"],"alternatives":alternatives})
        return {"source_sha256":wsd["source_sha256"],"providers":self.provenance,
                "targets":result,"interpretation":"Published role inventories, not assigned sentence arguments; all verbal sense alternatives retained."}
