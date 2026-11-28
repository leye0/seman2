"""Independent lexical and NLP providers. No ranking, rules or MRS rewriting.

The adapter translates provider APIs into JSON while retaining their own labels,
identifiers, source spans and alternatives. A lookup is not word-sense selection.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree

class Knowledge:
    def __init__(self, model="en_core_web_sm"):
        import spacy
        from nltk.corpus import wordnet, framenet
        from nltk.corpus.reader import VerbnetCorpusReader
        from nltk.corpus.util import LazyCorpusLoader
        verbnet3=LazyCorpusLoader('verbnet3', VerbnetCorpusReader, r'(?!\.).*\.xml')
        self.nlp=spacy.load(model)
        self.wn=wordnet
        self.vn=verbnet3
        self.fn=framenet
        # Fail fast if an enabled resource is absent instead of silently
        # pretending that a missing dictionary contains no matching entries.
        self.wn.ensure_loaded()
        self.vn.ensure_loaded()
        self.fn.ensure_loaded()
        self.provenance={"spacy":version("spacy"),"model":model,
                         "model_version":self.nlp.meta["version"],
                         "pipeline":list(self.nlp.pipe_names),
                         "nltk":version("nltk"),"wordnet":self.wn.get_version(),
                         "verbnet":"NLTK verbnet3 (3.3)",
                         "framenet":"NLTK framenet_v17 (1.7)"}

    @lru_cache(maxsize=8192)
    def wordnet(self, surface):
        return [{"id":s.name(),"pos":s.pos(),"lexname":s.lexname(),
                 "definition":s.definition(),"examples":s.examples(),
                 "lemmas":[{"name":l.name(),"key":l.key(),"count":l.count(),
                            "verb_frames":l.frame_strings()} for l in s.lemmas()],
                 "hypernyms":[h.name() for h in s.hypernyms()]}
                for s in self.wn.synsets(surface)]

    @lru_cache(maxsize=8192)
    def verbnet(self, lemma):
        return [{"class_id":cid,"thematic_roles":self.vn.themroles(cid),
                 "frames":self.vn.frames(cid),
                 "native_xml":ElementTree.tostring(self.vn.vnclass(cid),encoding="unicode")}
                for cid in self.vn.classids(lemma=lemma)]

    @lru_cache(maxsize=8192)
    def framenet(self, lemma):
        # Exact lexical-unit lookup, not a hand-written mapping of verbs to frames.
        units=self.fn.lus(r"(?i)^"+re.escape(lemma)+r"\.[^.]+$")
        rows=[]
        for lu in units:
            frame=self.fn.frame(lu.frame.ID)
            rows.append({"lu_id":lu.ID,"lu_name":lu.name,"frame_id":frame.ID,
                         "frame_name":frame.name,"frame_definition":frame.definition,
                         "frame_elements":[{"id":fe.ID,"name":fe.name,"core_type":fe.coreType,
                                            "definition":fe.definition}
                                           for fe in frame.FE.values()]})
        return rows

    def inspect(self, text):
        doc=self.nlp(text)
        tokens=[]
        lexicon={}
        for t in doc:
            if t.text!=text[t.idx:t.idx+len(t.text)]:
                raise ValueError("Provider token source offset mismatch")
            tokens.append({"text":t.text,"span":[t.idx,t.idx+len(t.text)],
                           "lemma":t.lemma_,"pos":t.pos_,"tag":t.tag_,
                           "morphology":t.morph.to_dict(),"dependency":t.dep_,
                           "head_token_index":t.head.i,"token_index":t.i,
                           "entity_iob":t.ent_iob_,"entity_type":t.ent_type_})
            if not t.is_alpha: continue
            for key in dict.fromkeys((t.text,t.lemma_)):
                if not key or key in lexicon: continue
                lexicon[key]={"wordnet":self.wordnet(key),
                              "verbnet":self.verbnet(key),
                              "framenet":self.framenet(key)}
        return {"source_text":text,"source_sha256":sha256(text.encode()).hexdigest(),
                "providers":self.provenance,"tokens":tokens,
                "entities":[{"text":e.text,"label":e.label_,"span":[e.start_char,e.end_char]}
                            for e in doc.ents],
                "lexicon":lexicon,"interpretation":"Independent provider outputs; not selected senses or ERG corrections."}


class Wiktionary:
    """Optional explicit word lookups, never transmit the user's paragraph.

    Use the MediaWiki API's native page revision and wikitext, not a home-made
    parser for Wiktionary's sense templates. No implicit network requests.
    """
    endpoint="https://en.wiktionary.org/w/api.php"
    def __init__(self, user_agent="Seman2 research lexical lookup/0.1 (https://github.com/leye0/seman2)"):
        self.user_agent=user_agent

    @lru_cache(maxsize=256)
    def lookup(self, word):
        q=urlencode({"action":"query","prop":"revisions","rvprop":"ids|content",
                     "rvslots":"main","titles":word,"redirects":"1","format":"json",
                     "formatversion":"2"})
        url=self.endpoint+"?"+q
        try:
            with urlopen(Request(url,headers={"User-Agent":self.user_agent,"Accept":"application/json"}),timeout=15) as f:
                raw=f.read()
            data=json.loads(raw)
            if "error" in data:
                return {"word":word,"status":"provider_error","error":data["error"],"url":url}
            pages=data["query"]["pages"]
            return {"word":word,"status":"missing" if all(p.get("missing") for p in pages) else "available",
                    "url":url,"response_sha256":sha256(raw).hexdigest(),"response":data}
        except (HTTPError,URLError,TimeoutError,ValueError,KeyError) as e:
            return {"word":word,"status":"provider_error","error":str(e),"url":url}
