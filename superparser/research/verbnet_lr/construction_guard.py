"""Experimental generic morphology/construction checks on one chosen tree.

Research-only. No sentence-specific exceptions, no parse forest. Closed English
paradigms are explicit; open-class checks abstain if evidence is insufficient.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Check:
    acceptable: bool
    reason: str = ""

def _features(c):
    f = c.features
    return f.as_dict() if hasattr(f, "as_dict") else f

def _leaves(node):
    c = getattr(node, "candidate", None)
    if c is not None:
        yield c
    else:
        for ch in getattr(node, "children", ()):
            yield from _leaves(ch)

def _walk(root):
    yield root
    for ch in getattr(root, "children", ()):
        yield from _walk(ch)

def _head(node):
    for c in reversed(tuple(_leaves(node))):
        if c.category in {"N", "PROPER-NOUN", "PRONOUN", "PRON"}:
            return c
    return None

def _subject(c):
    if c is None: return (None, None)
    w = c.surface.casefold()
    paradigm = {"i": ("singular","1"), "you":(None,"2"),
                "he":("singular","3"), "she":("singular","3"),
                "it":("singular","3"), "we":("plural","1"),
                "they":("plural","3")}
    if c.category in {"PRON", "PRONOUN"} and w in paradigm:
        return paradigm[w]
    n = _features(c).get("number")
    if n in {"singular","plural"}: return (n,"3")
    if c.category == "PROPER-NOUN": return ("singular","3")
    return (None,None)

def _finite_agreement(subject, verb, modal_forms=frozenset()):
    n, p = _subject(subject)
    if p is None: return Check(True)
    s = verb.surface.casefold()
    if verb.category in {"COPULA","AUX-BE"} and s in {"am","is","are","was","were"}:
        if p == "1" and n == "singular": good = {"am","was"}
        elif p == "2": good = {"are","were"}
        elif n == "singular": good = {"is","was"}
        elif n == "plural": good = {"are","were"}
        else: return Check(True)
        return Check(s in good, "finite_be_subject_agreement")
    if verb.category == "HAVE" and s in {"have","has"}:
        return Check(s == ("has" if p == "3" and n == "singular" else "have"),
                     "finite_have_subject_agreement")
    if verb.category == "AUX" and s in {"do","does"}:
        return Check(s == ("does" if p == "3" and n == "singular" else "do"),
                     "finite_do_subject_agreement")
    if verb.category == "V":
        lemma = verb.lemma.casefold()
        # A surface with an attested MODAL analysis cannot also stand as
        # uninflected third-person singular PRESENT of a regular lexical V.
        # The alternate verb reading remains possible for other subjects.
        # Closed-class membership is supplied by the lexical lattice.
        if ((n,p) == ("singular","3")
                and verb.surface.casefold() == lemma
                and lemma in modal_forms):
            return Check(False, "modal_homograph_uninflected_lexical_verb")
        if s != lemma and s.endswith("s") and not s.endswith("ss"):
            if (n,p) != ("singular","3"):
                return Check(False, "lexical_verb_third_singular_agreement")
    return Check(True)

def _bare_after_aux(seq, start):
    for c in seq[start:]:
        if c.category == "NEG": continue
        if c.category in {"MODAL","AUX","AUX-BE","COPULA","HAVE"}:
            return Check(True)  # secondary auxiliary; avoid over-claim
        if c.category == "V":
            return Check(c.surface.casefold() == c.lemma.replace("_"," ").casefold(),
                         "bare_verb_required_after_modal_or_do")
        return Check(True)
    return Check(True)

class ConstructionGuard:
    def __init__(self, modal_forms=frozenset()):
        self.modal_forms = frozenset(modal_forms)

    def validate(self, root):
        if root is None: return Check(False, "missing_tree")
        # Clause/VP/NP checks visit overlapping subtrees. Without a cache,
        # every ancestor flattens the same descendant leaves repeatedly;
        # nested clauses make those repeated walks quadratic. Cache only
        # per validation call, keyed by identity (ReadNode is immutable).
        leaf_cache = {}

        def leaves(node):
            key = id(node)
            if key not in leaf_cache:
                candidate = getattr(node, "candidate", None)
                if candidate is not None:
                    leaf_cache[key] = (candidate,)
                else:
                    leaf_cache[key] = tuple(
                        candidate for child in getattr(node, "children", ())
                        for candidate in leaves(child)
                    )
            return leaf_cache[key]

        def head(node):
            return next((c for c in reversed(leaves(node))
                         if c.category in {"N", "PROPER-NOUN", "PRONOUN", "PRON"}), None)

        for node in _walk(root):
            children = getattr(node, "children", ())
            # Morphology must support the candidate's selected grammatical
            # form: a surface such as "did" cannot be a BASE reading of "do".
            candidate = getattr(node, "candidate", None)
            if candidate is not None and candidate.category == "V":
                vform = _features(candidate).get("vform")
                if vform == "base" and (
                    candidate.surface.casefold() != candidate.lemma.casefold()
                ):
                    return Check(False, "surface_not_base_verb")
            if node.category == "NP" and children:
                lex = leaves(node)
                nominal_head = head(node)
                if lex and nominal_head is not None:
                    word = lex[0].surface.casefold()
                    n = _subject(nominal_head)[0]
                    if lex[0].category == "DET" and word in {"a","an","this","that","each","every"} and n == "plural":
                        return Check(False, "singular_determiner_plural_head")
                    if lex[0].category == "DET" and word in {"these","those"} and n == "singular":
                        return Check(False, "plural_determiner_singular_head")
            if node.category == "CLAUSE" and len(children) >= 2 and children[0].category == "NP":
                subj = head(children[0])
                for ch in children[1:]:
                    verb = next((v for v in leaves(ch) if v.category in
                                {"V","COPULA","AUX-BE","HAVE","AUX","MODAL"}), None)
                    if verb is not None:
                        if verb.category != "MODAL":
                            check = _finite_agreement(subj,verb,self.modal_forms)
                            if not check.acceptable: return check
                        break
            if node.category == "VP" and children:
                rule = getattr(getattr(node, "rule", None), "rule_id", None)
                if rule == "vp_obj_pred":
                    lexical_head = next((v for v in leaves(children[0]) if v.category == "V"),None)
                    if lexical_head is not None:
                        subcat = _features(lexical_head).get("subcat")
                        if subcat is not None and "complex_transitive" not in str(subcat):
                            return Check(False, "object_predicate_requires_complex_transitive")
            if children:
                lex = tuple(v for ch in children for v in leaves(ch))
                for i,v in enumerate(lex):
                    if v.category == "MODAL" or (
                        v.category == "AUX" and v.lemma.casefold() == "do"):
                        check = _bare_after_aux(lex,i+1)
                        if not check.acceptable: return check
        return Check(True)
