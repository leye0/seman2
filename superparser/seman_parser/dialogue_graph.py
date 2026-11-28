"""A source-linked discourse graph over independent native MRS readings.

No variable is shared across native readings, and no source relation is
promoted to a native ARG edge. Discontinuous speech is an explicit additional
ERG input view; every character maps to an original source character.
"""
from __future__ import annotations

from collections import defaultdict
import re
from .quoted_discourse import _REPORTING_VERB

QUOTE_KINDS = {"direct_speech", "embedded_quotation"}
PART_KINDS = {"spoken_clause_candidate", "reporting_clause", "narratorial_parenthetical"}
DIALOGUE_KINDS = QUOTE_KINDS | PART_KINDS | {"split_direct_speech_turn"}
EXTRA_REPORT = re.compile(r"(?i)\b(?:promised|vowed|interposed)\b")


def source_view(text, spans):
    """Build a view from ordered, nonoverlapping exact source ranges."""
    pieces, mapping, cursor, previous = [], [], 0, 0
    for a, b in spans:
        if not previous <= a < b <= len(text):
            raise ValueError("Invalid or overlapping source-view ranges")
        pieces.append(text[a:b])
        mapping.append([cursor, cursor+b-a, a, b])
        cursor += b-a
        previous = b
    return {"text": "".join(pieces), "source_map": mapping}


def remap(mapping, start, end):
    """Project a native character span to zero or more exact source ranges."""
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or start >= end:
        return []
    result = []
    for a,b,c,d in mapping:
        lo,hi=max(a,start),min(b,end)
        if lo<hi:
            result.append([c+lo-a,c+hi-a])
    if sum(b-a for a,b in result)!=end-start:
        return []
    return result


def resumed_views(text, parts):
    """Quote interiors in source order; preserve a comma or explicitly omit
    an intercalation-final comma. Never add a word, punctuation or whitespace.
    A separator is an existing whitespace character between the quotes.
    """
    byid={p["id"]:p for p in parts}
    for turn in parts:
        if turn["function"]!="split_direct_speech_turn":
            continue
        reporters=[p for p in parts if p["function"]=="reporting_clause"
                   and p.get("governor")==turn["id"]]
        if len(reporters)!=1:
            continue
        tag=reporters[0]
        first=[p for p in parts if p["function"]=="direct_speech"
               and p.get("governor")==tag["id"] and p["relation"]=="reported_content"]
        if len(first)!=1:
            continue
        chain=first[:]
        while True:
            follow=[p for p in parts if p["function"]=="direct_speech"
                    and p.get("governor")==chain[-1]["id"]
                    and p["relation"]=="resumption_of_split_speech"]
            if len(follow)!=1 or follow[0] in chain:
                break
            chain.append(follow[0])
        if len(chain)<2:
            continue
        for drop in (False,True):
            spans=[]
            omitted=[]
            valid=True
            for i,q in enumerate(chain):
                a,b=q["start"]+1,q["end"]-1
                while a<b and text[a].isspace(): a+=1
                while a<b and text[b-1].isspace(): b-=1
                if i<len(chain)-1 and drop and a<b and text[b-1]==",":
                    omitted.append([b-1,b])
                    b-=1
                if a>=b:
                    valid=False; break
                if i:
                    gap=range(chain[i-1]["end"],q["start"])
                    sep=next((n for n in gap if text[n]==" "),None)
                    if sep is None:
                        valid=False; break
                    spans.append((sep,sep+1))
                spans.append((a,b))
            if not valid or (drop and not omitted):
                continue
            view=source_view(text,spans)
            yield {"id":turn["id"]+(":without_intercalation_comma" if drop else ":punctuation_preserved"),
                   "kind":"resumed_speech", "source_id":turn["id"],
                   "quote_ids":[q["id"] for q in chain],
                   "omitted_intercalation_commas":omitted,**view}


def project(result, view):
    """JSON projection retaining native variable features, EPs and constraints.
    Namespacing is by view AND rank. No cross-reading MRS unification.
    """
    from delphin.codecs import simplemrs
    mrs=simplemrs.decode(result["mrs"])
    rid=view["id"]+"/rank"+str(result["native_rank"])
    def ref(var):
        return rid+"/"+var if var is not None else None
    variables={ref(v):dict(f) for v,f in mrs.variables.items()}
    eps=[]
    for i,ep in enumerate(mrs.rels):
        spans=remap(view["source_map"],ep.cfrom,ep.cto)
        args={k:(v if k=="CARG" else ref(v)) for k,v in ep.args.items()}
        eps.append({"id":rid+"/ep"+str(i),"predicate":ep.predicate,
                    "label":ref(ep.label),"args":args,"view_span":[ep.cfrom,ep.cto],
                    "source_spans":spans})
    return {"id":rid,"view_id":view["id"],"native_rank":result["native_rank"],
            "quality_flags":result["quality_flags"],"top":ref(mrs.top),"index":ref(mrs.index),
            "variables":variables,"predications":eps,
            "hcons":[{"hi":ref(h.hi),"relation":h.relation,"lo":ref(h.lo)} for h in mrs.hcons],
            "icons":[{"left":ref(i.left),"relation":i.relation,"right":ref(i.right)} for i in mrs.icons]}


def wholly_in(ep, part):
    return bool(ep["source_spans"]) and all(part["start"]<=a<b<=part["end"] for a,b in ep["source_spans"])


def cross_quote_links(reading, quotes):
    """Native shared variables or qeq handles across separately quoted spans.
    Shared-variable edges name the native argument slot, not a guessed role.
    """
    eps=reading["predications"]
    owners={ep["id"]:next((q["id"] for q in quotes if wholly_in(ep,q)),None) for ep in eps}
    byvar=defaultdict(list)
    bylabel=defaultdict(list)
    qeq=defaultdict(list)
    for ep in eps:
        if ep["args"].get("ARG0"): byvar[ep["args"]["ARG0"]].append(ep)
        bylabel[ep["label"]].append(ep)
    for h in reading["hcons"]:
        if h["relation"]=="qeq": qeq[h["hi"]].append(h["lo"])
    edges=[]
    for ep in eps:
        owner=owners[ep["id"]]
        if owner is None or not ep["predicate"].startswith("_"): continue
        for role,v in ep["args"].items():
            if not re.fullmatch(r"ARG[1-9][0-9]*",role): continue
            candidates=[("shared_variable",t) for t in byvar[v]]
            for lo in qeq[v]:
                candidates.extend(("qeq_scope",t) for t in bylabel[lo])
            for mechanism,t in candidates:
                other=owners[t["id"]]
                if other is None or other==owner or not (t["predicate"].startswith("_") or t["predicate"] in {"pron","named"}):
                    continue
                edges.append({"from":ep["id"],"to":t["id"],"argument":role,
                              "mechanism":mechanism,"from_quote":owner,"to_quote":other,
                              "signature":[ep["predicate"],ep["source_spans"],role,t["predicate"],t["source_spans"],mechanism]})
    return edges


def report_evidence(text, tag, reading):
    """Find native reporting-predicate evidence at the source tag's overt cue.
    ARG1 is only a speaker CANDIDATE, and requires an overt entity anchor.
    An inverted tag parsed as an imperative must not invent its subject.
    """
    surface=text[tag["start"]:tag["end"]]
    cue=_REPORTING_VERB.search(surface) or EXTRA_REPORT.search(surface)
    if cue is None: return []
    a,b=tag["start"]+cue.start(),tag["start"]+cue.end()
    eps=reading["predications"]
    evidence=[]
    for ep in eps:
        pred=ep["predicate"].strip('"')
        if not ("_v_" in pred and wholly_in(ep,tag) and any(x<=a<b<=y for x,y in ep["source_spans"])):
            continue
        speaker=ep["args"].get("ARG1")
        if not speaker or not speaker.rsplit("/",1)[-1].startswith("x"): speaker=None
        anchors=[]
        if speaker:
            for t in eps:
                if t["args"].get("ARG0")!=speaker or not wholly_in(t,tag):
                    continue
                p=t["predicate"].strip('"')
                if p in {"pron","named"} or "_n_" in p:
                    anchors.extend(t["source_spans"])
        anchors=sorted({tuple(x) for x in anchors})
        evidence.append({"reading_id":reading["id"],"predicate_id":ep["id"],
                         "event":ep["args"].get("ARG0"),"speaker_variable":speaker if anchors else None,
                         "speaker_source_spans":[list(x) for x in anchors],
                         "quality_flags":reading["quality_flags"],"reporting_cue_span":[a,b]})
    return evidence


def compose_dialogue(text, parts, whole, components, parse=None):
    """One source-linked graph, with mutually exclusive reading alternatives.

    Source edges identify attribution and resumption; native edges stay inside
    their individual MRS. Additional cross-view links are typed hypotheses.
    """
    if not any(p["function"] in QUOTE_KINDS for p in parts): return None
    parts=list(parts)
    byid={p["id"]:p for p in parts}
    if len(byid)!=len(parts): raise ValueError("Duplicate source constituent")
    for p in parts:
        if not 0<=p["start"]<p["end"]<=len(text): raise ValueError("Invalid source constituent")
        if p.get("governor") is not None and p["governor"] not in byid:
            raise ValueError("Missing source governor")
    views=[{"id":"whole","kind":"whole","source_id":None,**source_view(text,[(0,len(text))]),"analysis":whole}]
    for c in components:
        part=byid[c["component_id"]]
        a,b=c["unit_span"]
        if [a,b]!=[part["start"],part["end"]]: raise ValueError("Component span drift")
        view=source_view(text,[(a,b)])
        if c["analysis"]["source_text"]!=view["text"]: raise ValueError("Component source drift")
        views.append({"id":"component:"+part["id"],"kind":"component","source_id":part["id"],**view,"analysis":c["analysis"]})
    if parse is not None:
        for v in resumed_views(text,parts):
            views.append({**v,"analysis":parse(v["text"])})
    readings=[]
    view_index={}
    for v in views:
        rs=[]
        if v["analysis"].get("source_text",v["text"])!=v["text"]: raise ValueError("Native view source drift")
        for result in v["analysis"].get("results",[]):
            if result.get("mrs") and "mrs_decode_error" not in result.get("quality_flags",[]):
                rd=project(result,v)
                readings.append(rd)
                rs.append(rd["id"])
        view_index[v["id"]]=rs
    rdindex={x["id"]:x for x in readings}
    quote_nodes=[p for p in parts if p["function"] in QUOTE_KINDS]
    edges=[{"kind":"source_hypothesis","from":p["id"],"to":p["governor"],
            "relation":p["relation"],"evidence":p["evidence"]}
           for p in parts if p.get("governor") is not None and p["function"] in DIALOGUE_KINDS]
    attributions=[]
    for quote in quote_nodes:
        if quote["function"]!="direct_speech": continue
        current=quote; chain=[current["id"]]
        while current["relation"]=="resumption_of_split_speech" and current.get("governor") in byid:
            nxt=byid[current["governor"]]
            if nxt["id"] in chain: raise ValueError("Cyclic resumption")
            chain.append(nxt["id"]); current=nxt
        tag=byid.get(current.get("governor"))
        if current["relation"]!="reported_content" or not tag or tag["function"]!="reporting_clause":
            continue
        native=[]
        for rid in view_index["whole"]+view_index.get("component:"+tag["id"],[]):
            native.extend(report_evidence(text,tag,rdindex[rid]))
        candidates=[e for e in native if e["speaker_variable"]]
        whole_candidates=[e for e in candidates if e["reading_id"].startswith("whole/")]
        preferred=whole_candidates or candidates
        # Rank 1 is not privileged over contradictory overt speaker evidence.
        # Surface agreement is reported as such, not as resolved identity.
        groups=defaultdict(list)
        for e in preferred:
            groups[tuple(tuple(s) for s in e["speaker_source_spans"])].append(e)
        speaker_options=[{"source_spans":[list(s) for s in key],"evidence":val}
                         for key,val in groups.items()]
        attr={"quote_id":quote["id"],"reporting_clause_id":tag["id"],"source_chain":chain,
              "status":"one_anchored_candidate" if len(groups)==1 else "ambiguous" if groups else "unresolved",
              "speaker_options":speaker_options,"native_report_evidence":native,
              "preferred_basis":"whole" if whole_candidates else "component" if candidates else "source_only"}
        attributions.append(attr)
        edges.append({"kind":"source_hypothesis","from":quote["id"],"to":tag["id"],
                      "relation":"reported_by_candidate","source_chain":chain})
        for e in native:
            edges.append({"kind":"cross_view_hypothesis","from":e["predicate_id"],"to":quote["id"],
                          "relation":"reporting_event_for_quotation_candidate","reading_id":e["reading_id"]})
        # Deictic links attach to the source attribution, never identify native
        # variables across readings. Exclude embedded quotation context.
        nested=[q for q in quote_nodes if q["function"]=="embedded_quotation"
                and quote["start"]<q["start"]<q["end"]<quote["end"]]
        for rd in readings:
            for ep in rd["predications"]:
                if ep["predicate"]!="pron" or not wholly_in(ep,quote) or any(wholly_in(ep,q) for q in nested):
                    continue
                v=ep["args"].get("ARG0")
                f=rd["variables"].get(v,{})
                if f.get("PERS")=="1" and f.get("NUM")=="sg" and speaker_options:
                    edges.append({"kind":"cross_view_hypothesis","from":v,"to":quote["id"],
                                  "relation":"first_person_speaker_candidate","reading_id":rd["id"],
                                  "source_spans":ep["source_spans"]})
    bridges=[]
    for v in views:
        if v["kind"] not in {"whole","resumed_speech"}: continue
        qs=[byid[q] for q in v["quote_ids"]] if v["kind"]=="resumed_speech" else [q for q in quote_nodes if q["function"]=="direct_speech"]
        if len(qs)<2: continue
        for rid in view_index[v["id"]]:
            bridges.extend({"reading_id":rid,**e} for e in cross_quote_links(rdindex[rid],qs))
    # Whole and component raw analyses are already in the enclosing report;
    # preserve extra native resumed-view responses here, not copies of others.
    exposed_views=[]
    for v in views:
        entry={k:val for k,val in v.items() if k!="analysis"}
        entry["reading_ids"]=view_index[v["id"]]
        entry["status"]=v["analysis"]["status"]
        if v["kind"]=="resumed_speech": entry["analysis"]=v["analysis"]
        exposed_views.append(entry)
    return {"schema":"seman2-dialogue-graph-v1","source_nodes":parts,
            "views":exposed_views,"readings":readings,"edges":edges,
            "attributions":attributions,"native_cross_quote_links":bridges,
            "interpretation":"Native readings are alternatives, not a merged MRS. Cross-view hypotheses are not grammatical proof."}
