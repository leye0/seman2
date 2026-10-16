"""Read-only lexical lookup proxy to avoid provably absent multiword lookups.

This is a strict fast-negative filter; it never removes a candidate supported
by the static lexicon or WordNet lemma index. Inflected multiword surfaces are
passed through untouched because suffix stripping may recover a lemma.

No changes to shared Lexicon/WordNet objects and no permanent per-text cache.
"""
from __future__ import annotations

class FastMultiwordLexicon:
    __slots__ = ("original","_cache","precheck_rejections")

    def __init__(self, original):
        self.original=original
        self._cache={}
        self.precheck_rejections=0

    def __getattr__(self, key):
        return getattr(self.original,key)

    def _could_exist(self, surface):
        lex=self.original
        key=surface.casefold()
        if " " not in key:return True
        # Leave every regularly inflectable ending to the full morphology
        # resolver: "red cars" might be inflected "red car".
        if key.endswith(("s","ed","ing")):return True
        if (key in lex._by_surface or key in lex._by_lemma or
                key in lex._by_morph):
            return True
        wn=lex._wordnet
        if wn is not None and wn.lookup(key):
            return True
        return False

    def lookup_morphology(self, surface):
        key=surface.casefold()
        if key in self._cache:
            return self._cache[key]
        if not self._could_exist(key):
            self.precheck_rejections+=1
            result=()
        else:
            result=tuple(self.original.lookup_morphology(surface))
        self._cache[key]=result
        return result
