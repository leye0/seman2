"""Thin adapter to the upstream GlossBERT WSD engine; no sense heuristics."""
from __future__ import annotations
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import math

MODEL="kanishka/GlossBERT"
REVISION="0cc3b83"  # published model snapshot (resolved to full SHA by HF)
UPOS_TO_WN={"NOUN":"n","VERB":"v","ADJ":"a","ADV":"r"}

class WSD:
    def __init__(self, *, model=MODEL, revision=REVISION, cuda=False, backend=None):
        if backend is None:
            from huggingface_hub import snapshot_download
            from glossbert import GlossBERT
            from nltk.corpus import wordnet
            directory=snapshot_download(repo_id=model,revision=revision,
                allow_patterns=["config.json","pytorch_model.bin","model.safetensors",
                                "tokenizer.json","tokenizer_config.json","special_tokens_map.json","vocab.txt"])
            self.backend=GlossBERT(model=directory,cuda=cuda)
            self.provenance={"engine":"GlossBERT","package_version":version("glossbert"),
                "model":model,"revision":Path(directory).name,
                "wordnet":wordnet.get_version(),"device":str(self.backend.device),
                "torch":version("torch"),"transformers":version("transformers")}
        else:
            self.backend=backend
            self.provenance={"engine":"injected test backend"}

    def target(self,text,start,end,lemma,pos=None):
        if not 0<=start<end<=len(text) or not lemma:
            raise ValueError("Invalid target span or lemma")
        if pos not in (None,"n","v","a","s","r"):
            raise ValueError("Use a WordNet POS or None")
        # The upstream engine performs candidate retrieval, input marking,
        # neural classification and ranking. Preserve the returned order.
        raw=self.backend(text,start,end,lemma,pos=pos)
        alternatives=[]
        for score,synset in raw:
            score=float(score)
            if not math.isfinite(score):
                raise ValueError("Nonfinite upstream WSD score")
            alternatives.append({"id":synset.name(),"offset":synset.offset(),
                "pos":synset.pos(),"lexname":synset.lexname(),"definition":synset.definition(),
                "lemma_keys":[l.key() for l in synset.lemmas()],"score":score})
        return {"span":[start,end],"text":text[start:end],"lemma":lemma,"pos":pos,
            "status":"predicted" if alternatives else "no_wordnet_candidate",
            "prediction":alternatives[0] if alternatives else None,"alternatives":alternatives,
            "score_type":"upstream binary context-gloss match score; not calibrated across senses"}

    def inspect(self,text, tokens):
        """Use provider token offsets and standard UPOS/WordNet tag mapping."""
        rows=[]
        for t in tokens:
            pos=UPOS_TO_WN.get(t["pos"])
            if pos is None:
                continue
            a,b=t["span"]
            if text[a:b]!=t["text"]:
                raise ValueError("Token source offset mismatch")
            rows.append(self.target(text,a,b,t["lemma"],pos))
        return {"source_text":text,"source_sha256":sha256(text.encode()).hexdigest(),
            "provider":self.provenance,"targets":rows,
            "interpretation":"Independent contextual sense predictions, not changes to ERG MRS."}
