"""One-pass structural grammar consolidation (research; no sentence-specific patches).

Three GENERIC interfaces: (1) agreement feature transport from verbal
heads through VP to the subject; (2) modal/do-support base-form
selection; (3) complement-frame evidence and determiner agreement.

This overlay is opt-in, cloned from an unchanged original grammar. It
does not treat negative examples as training data and does not modify
the production parser. All lexical alternatives remain in the lattice.
"""
from __future__ import annotations

from dataclasses import replace
from collections import Counter

from seman_parser.engine import ParserResources
from seman_parser.features import FeatureStructure
from seman_parser.grammar import Grammar, GrammarRule, RuleSymbol


def _symbol(sym: RuleSymbol, *, features=None, add_requires=()):
    attrs=dict(sym.features.as_dict())
    attrs.update(features or {})
    return RuleSymbol(sym.category,FeatureStructure.build(attrs),
                      sym.exports,tuple(dict.fromkeys((*sym.requires,*add_requires))))


def consolidate_grammar(original: Grammar):
    changed=Counter()
    out=[]
    for rule in original.rules:
        rhs=list(rule.rhs)
        lhs=rule.lhs
        name=rule.rule_id

        # GENERAL NUMBER/PERSON PROPAGATION: the original subject -> VP
        # agreement constraint is ineffective if finite VP does not carry
        # its inflected head's feature. Transform each finite VP headed by
        # V, COPULA, HAVE, AUX-BE (and recursively by VP).
        if lhs.category=="VP" and rhs and rhs[0].category in (
            "V","COPULA","HAVE","AUX-BE","VP"):
            head=rhs[0]
            if "number" not in lhs.features.as_dict():
                lhs=_symbol(lhs,features={"number":"?agr_n","person":"?agr_p"})
                rhs[0]=_symbol(head,features={"number":"?agr_n","person":"?agr_p"})
                changed["vp_head_agreement_propagation"]+=1

        # Modal constructions require a bare verbal complement.
        # VP-NP is the existing classical bare-verb constituent, with
        # its original children/rules and semantic exports preserved.
        if name=="vp_modal" and len(rhs)==2 and rhs[1].category=="VP":
            rhs[1]=replace(rhs[1],category="VP-NP")
            changed["modal_base_form"]+=1

        # DO+NEG requires the BASE form, not a finite VP.
        if name=="clause_neg_vp" and len(rhs)==4 and rhs[3].category=="VP":
            rhs[3]=replace(rhs[3],category="VP-NP")
            changed["aux_base_form"]+=1

        # Verb + NP + NP cannot be an unrestricted object-predicate.
        # Frame evidence must positively license the valence.
        if name=="vp_obj_pred" and rhs and rhs[0].category=="V":
            rhs[0]=_symbol(rhs[0],features={"subcat":"complex_transitive"},
                           add_requires=("subcat",))
            changed["complex_transitive_evidence"]+=1

        # The grammatical determiner in this quantifier construction
        # must agree with the noun. This is a variable, not a word list.
        if name=="np_quant_n" and len(rhs)>=2 and rhs[0].category=="DET":
            rhs[0]=_symbol(rhs[0],features={"number":"?n"})
            changed["determiner_agreement"]+=1

        out.append(GrammarRule(rule.rule_id,tuple(rhs),lhs,
                               rule.score,rule.provenance))
    return Grammar(out),dict(changed)


class MorphologyProofLexicon:
    """Wrap existing lexicon to make inflected surfaces informative.

    Only project *grammatically witnessed morphology*: productive
    English third-person singular -s, plus the irregular BE paradigm
    already represented in the seed catalog. Do not alter scores, remove
    unrelated lexical readings, or invent unknown inflections.
    """

    _BE_FORMS={
        "is":("singular","3"),
        "are":("plural",None),
        "was":("singular",None),
        "were":("plural",None),
        "am":("singular","1"),
    }

    def __init__(self, lexicon):
        self._lexicon=lexicon
        self._calls=0
        self._reinforced=0
        self._filtered=0

    def __getattr__(self,name):
        return getattr(self._lexicon,name)

    def lookup_morphology(self,surface):
        rows=self._lexicon.lookup_morphology(surface)
        written=surface.casefold()
        updated=[]
        for entry,sense,lemma in rows:
            features=sense.features
            if lemma.casefold()=="be" and sense.category in ("COPULA","AUX-BE"):
                expected=self._BE_FORMS.get(written)
                if expected is not None:
                    number,person=expected
                    existing=features.as_dict()
                    if existing.get("number") not in (None,number):
                        self._filtered+=1
                        continue
                    if person is not None and existing.get("person") not in (None,person):
                        self._filtered+=1
                        continue
                    updated_values={"number":number}
                    if person is not None:updated_values["person"]=person
                    features=FeatureStructure.build({**existing,**updated_values})
            if sense.category=="V" and (
                written!=lemma.casefold()
                and written.endswith("s")
                and not lemma.casefold().endswith("s")
                and features.as_dict().get("vform")=="finite"
            ):
                features=FeatureStructure.build({
                    **features.as_dict(),"number":"singular","person":"3"})
            if features is not sense.features:
                self._reinforced+=1
                sense=replace(sense,features=features)
            updated.append((entry,sense,lemma))
        self._calls+=1
        return tuple(updated)

    def summary(self):
        return {"lookup_calls":self._calls,
                "morphology_enriched":self._reinforced,
                "irregular_readings_filtered":self._filtered}


def consolidated_resources(resources:ParserResources):
    grammar,changed=consolidate_grammar(resources.grammar)
    lexicon=MorphologyProofLexicon(resources.lexicon)
    derived=ParserResources(grammar,lexicon,resources.types,resources.metadata)
    return derived,changed
