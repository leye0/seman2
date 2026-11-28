"""Independent, source-anchored HanLP ModernBERT SRL adapter.

The upstream neural model finds predicates and all role spans in one pass.
No predicate lists, handcrafted linguistic inference or MRS mutation.
"""
from __future__ import annotations
from hashlib import sha256
from importlib.metadata import version
from collections.abc import Mapping

MODEL_URL="https://file.hankcs.com/hanlp/mtl/en_tok_lem_pos_ner_srl_udep_sdp_con_modernbert_large_prepend_false_20250107_181612.zip"
BASE_URL="https://file.hankcs.com/hanlp/mtl/en_tok_lem_pos_ner_srl_udep_sdp_con_modernbert_base_prepend_false_20241229_053838.zip"

def align(text,tokens):
    """Lossless sequential alignment; never silently invent normalized offsets."""
    spans=[]
    cursor=0
    for token in tokens:
        while cursor<len(text) and text[cursor].isspace(): cursor+=1
        if not token or not text.startswith(token,cursor):
            return None
        spans.append([cursor,cursor+len(token)])
        cursor+=len(token)
    return spans if not text[cursor:].strip() else None

def project(text,tokens,frames):
    spans=align(text,tokens)
    rows=[]
    for frame in frames:
        members=[]
        for member in frame:
            if len(member)!=4: raise ValueError("Unexpected native SRL member")
            surface,label,a,b=member
            if not isinstance(a,int) or not isinstance(b,int) or not 0<=a<b<=len(tokens):
                raise ValueError("Native token offset outside sentence")
            span=[spans[a][0],spans[b-1][1]] if spans is not None else None
            members.append({"native_text":surface,"label":label,"token_span":[a,b],
                            "source_span":span,"source_text":text[span[0]:span[1]] if span else None})
        predicates=[x for x in members if x["label"]=="PRED"]
        rows.append({"predicates":predicates,"arguments":[x for x in members if x["label"]!="PRED"],
                     "native_members":members,"status":"one_predicate" if len(predicates)==1 else "unexpected_predicate_count"})
    return {"source_text":text,"source_sha256":sha256(text.encode()).hexdigest(),
            "tokens":[{"text":t,"source_span":spans[i] if spans is not None else None} for i,t in enumerate(tokens)],
            "alignment":"exact" if spans is not None else "unmapped_native_tokens",
            "frames":rows,"native_srl":frames}

class SRL:
    def __init__(self, *, model=MODEL_URL, cuda=False, backend=None):
        if backend is None:
            import hanlp
            self.backend=hanlp.load(model,devices=0 if cuda else -1)
            self.provenance={"engine":"HanLP","version":version("hanlp"),
                             "model":model,"device":"cuda:0" if cuda else "cpu",
                             "torch":version("torch"),"transformers":version("transformers"),
                             "inventory":"native English SRL (PropBank-style span labels)"}
        else:
            self.backend=backend
            self.provenance={"engine":"injected test backend"}

    def inspect_many(self,texts):
        texts=list(texts)
        if not texts: return []
        if any(not isinstance(t,str) or not t.strip() for t in texts):
            raise ValueError("SRL requires nonempty source strings")
        # List-of-strings deliberately represents one source unit per input.
        # The model itself tokenizes and detects every predicate.
        native=self.backend(texts,tasks=["tok","srl"])
        if not isinstance(native,Mapping): raise ValueError("Expected native HanLP Document")
        tok_keys=[k for k in native if k=="tok" or k.startswith("tok/")]
        if len(tok_keys)!=1 or "srl" not in native:
            raise ValueError("Unexpected native task keys: "+repr(list(native)))
        tokens,frames=native[tok_keys[0]],native["srl"]
        if len(tokens)!=len(texts) or len(frames)!=len(texts):
            raise ValueError("Native batch cardinality mismatch")
        return [{**project(t,ts,fs),"provider":self.provenance}
                for t,ts,fs in zip(texts,tokens,frames)]

    def inspect(self,text):
        return self.inspect_many([text])[0]
