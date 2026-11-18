"""Proof-bearing literary constructions with explicit attachment boundaries."""
from __future__ import annotations

import re

from .scoped_novel_1000 import L, M, P, _planner

JOURNEY_RELATIVE = "structural_interval_with_nominal_destination_and_relative"
OBJECT_RELATIVE = "structural_modal_question_with_parallel_object_gaps"
PERCEPTION_GESTURE = "structural_perception_location_and_shared_agent_gesture"
PARALLEL_INVERSION = "structural_parallel_emphatic_do_with_vocative"
REPORT_COMMAND = "dialogue_coordinated_report_with_temporal_imperative"
RECOVERY_RELATIVE = "structural_recovery_relative_with_nested_object_gap"
PERCEIVED_REACTION = "structural_vocative_perfect_and_negative_perception_question"
POSSESSIVE_COORDINATION = "structural_shared_agent_creation_and_possessive_relative"
RECOGNITION_CONTEXT = "structural_coordinated_copular_affect_and_perception_with_context"
DIALECT_CAUSE = "dialogue_split_interjection_and_gerundial_cause"
NEGATIVE_REPRISE = "dialogue_split_negative_response_and_do_ellipsis"
ADMISSION = "structural_shared_subject_motion_and_admission_with_gerund"

# These plans recognize the overt configuration. Each open-class piece needs
# an exact lexical edge or a ranked phrase proof in the existing composer.
_W = r"[A-Za-z]+(?:[-’'][A-Za-z]+)*"
_NOM = rf"{_W}(?: +{_W}){{0,7}}"
_POSSESSIVE = r"(?:my|your|his|her|our|their)"
_SUBJECT = r"(?:I|you|he|she|it|we|they)"
_DESTINATION = r"[A-Z][a-z]+(?: +[A-Z][a-z]+){0,2}"


def S(group, category, **features):
    return group, category, "scoped-lexical", features


PLANS = (
    (
        JOURNEY_RELATIVE,
        re.compile(
            rf"(?P<subject>{_SUBJECT}) +(?P<have>had) +(?P<degree>sufficient|ample|little|enough) +"
            rf"(?P<leisure>leisure|time|opportunity) +(?P<for>for) +(?P<topics>these|those) +(?P<and0>and) +(?P<topic>{_NOM}?) +"
            rf"(?P<during>during) +(?P<interval>{_POSSESSIVE} +(?:journey|voyage|trip|walk|drive)) +"
            rf"(?P<to>to) +(?P<goal>{_DESTINATION})(?P<comma>,) +(?P<which>which) +"
            rf"(?P<be>was|is) +(?P<quality>long|brief|short|arduous|slow) +(?P<and>and) +"
            rf"(?P<participle>fatiguing|tiring|exhausting|taxing|demanding|draining)(?P<stop>\.)",
        ),
        (
            P("subject", "NP"), L("have", "V", vform="finite", lemma_in="have", subcat_member="transitive"),
            L("degree", "ADJ"), L("leisure", "N", attested_reading="true"), L("for", "PREP"),
            P("topics", "NP"), L("and0", "COORD"), P("topic", "NP"), L("during", "PREP"), P("interval", "NP", proof_rule="np_poss"),
            L("to", "PREP"), P("goal", "NP"), M("comma", "COMMA"), L("which", "WH-PRONOUN"),
            L("be", "COPULA", vform="finite"), L("quality", "ADJ"), L("and", "COORD"),
            S("participle", "ADJ", participial_property="true"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        OBJECT_RELATIVE,
        re.compile(
            rf"(?P<and>And|But) +(?P<why>why) +(?P<modal>should|could|would|must) +"
            rf"(?P<subject>{_SUBJECT}) +(?P<describe>describe|recall|mention|explain|recount) +"
            rf"(?P<theme>(?:a|the|this|that) +{_NOM}?) +(?P<which>which|that) +"
            rf"(?P<alls>all|we|you|they|many|everyone|everybody|people) +(?P<have>have|has) +"
            rf"(?P<done>{_W})(?P<comma>,) +(?P<and2>and) +(?P<must>must|will|might|may|can|could|should) +"
            rf"(?P<again>{_W})(?P<question>\?)",
        ),
        (
            L("and", "COORD"), L("why", "WH-NOM"), L("modal", "MODAL", vform="finite"),
            P("subject", "NP"), L("describe", "V", vform="base", subcat_member="transitive"),
            P("theme", "NP", simple_nominal_proof="true"), L("which", "WH-PRONOUN"),
            P("alls", "NP", proof_rule="np_indef_pron"), L("have", "HAVE", vform="finite"),
            L("done", "V", vform="ed", subcat_member="transitive"), M("comma", "COMMA"),
            L("and2", "COORD"), L("must", "MODAL", vform="finite"),
            L("again", "V", vform="base", subcat_member="transitive"), M("question", "QMARK"),
        ),
        "finite",
    ),
    (
        PERCEPTION_GESTURE,
        re.compile(
            rf"(?P<subject>(?:The|A|Her|His) +{_NOM}?) +(?P<see>saw|noticed|read|detected|recognized) +"
            rf"(?P<state>{_POSSESSIVE} +{_NOM}?) +(?P<in>in) +"
            rf"(?P<location>{_POSSESSIVE} +(?:face|eyes|expression|gaze)) +(?P<and>and) +"
            rf"(?P<gesture>gnashed|clenched|gritted|pressed) +"
            rf"(?P<limb>{_POSSESSIVE} +(?:teeth|fists|jaw|lips)) +(?P<manner>in) +"
            rf"(?P<affect>(?:the +(?:impotence|intensity|depths) +of +)?"
            rf"(?:anger|fury|frustration|rage|fear|despair|grief|agitation))(?P<stop>\.)",
        ),
        (
            P("subject", "NP", simple_nominal_proof="true"),
            L("see", "V", vform="finite", lemma_in="see|notice|read|detect|recognize",
              subcat_member="transitive"),
            P("state", "NP", proof_rule="np_poss"), L("in", "PREP"),
            P("location", "NP", proof_rule="np_poss"), L("and", "COORD"),
            L("gesture", "V", vform="finite", lemma_in="gnash|clench|grit|press",
              subcat_member="transitive"),
            P("limb", "NP", proof_rule="np_poss"), L("manner", "PREP"),
            P("affect", "NP"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        PARALLEL_INVERSION,
        re.compile(
            rf"(?P<again>Again|Still|Thus) +(?P<do>do|does|did) +(?P<subject>{_SUBJECT}) +"
            rf"(?P<vow>vow|swear|seek|promise|demand) +(?P<vowed>{_NOM}?)(?P<semi>;) +"
            rf"(?P<again2>again|still|thus) +(?P<do2>do|does|did) +(?P<subject2>{_SUBJECT}) +"
            rf"(?P<devote>devote|consign|commit|condemn|sentence) +"
            rf"(?P<target>thee|you|him|her|them|us)(?P<comma>,) +(?P<vocative>{_W} +{_W})"
            rf"(?P<comma2>,) +(?P<to>to) +(?P<fate>{_NOM})(?P<stop>\.)",
        ),
        (
            L("again", "ADV"), L("do", "AUX", vform="finite"), P("subject", "NP"),
            L("vow", "V", vform="base", subcat_member="transitive"), P("vowed", "NP"),
            M("semi", "SEMICOLON"), L("again2", "ADV"), L("do2", "AUX", vform="finite"),
            P("subject2", "NP"), L("devote", "V", vform="base", attested_reading="true"),
            S("target", "PRONOUN"), M("comma", "COMMA"),
            P("vocative", "NP", simple_nominal_proof="true"), M("comma2", "COMMA"),
            L("to", "PREP"), P("fate", "NP"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        REPORT_COMMAND,
        re.compile(
            rf'(?P<subject>{_SUBJECT}) +(?P<move>started|stepped|moved|sprang|drew|turned) +'
            rf'(?P<direction>forward|back|aside|round) +(?P<and>and) +'
            rf'(?P<report>exclaimed|cried|shouted|called)(?P<comma>,) +(?P<open>["“‘])'
            rf'(?P<voc>{_W})(?P<excl>!) +(?P<before>Before|After) +'
            rf'(?P<actor>you) +(?P<act>{_W}) +(?P<object>(?:my|your|the) +{_NOM}?)(?P<comma2>,) +'
            rf'(?P<be>be) +(?P<certainty>sure|certain) +(?P<that>that) +'
            rf'(?P<you>you) +(?P<are>are) +(?P<emph>yourself|yourselves) +'
            rf'(?P<state>{_W})(?P<stop>\.)(?P<close>["”’])',
        ),
        (
            P("subject", "NP"), L("move", "V", vform="finite", subcat_member="intransitive"),
            L("direction", "ADV"), L("and", "COORD"), L("report", "V", vform="finite"),
            M("comma", "COMMA"), M("open", "OPEN-QUOTE"), L("voc", "N", attested_reading="true"),
            M("excl", "EXCL"), L("before", "CONJ"), P("actor", "NP"),
            L("act", "V", vform="base", subcat_member="transitive"), P("object", "NP"),
            M("comma2", "COMMA"), L("be", "COPULA", vform="base"), L("certainty", "ADJ", clausal_complement="true"),
            L("that", "COMP-THAT"), P("you", "NP"), L("are", "COPULA", vform="finite"),
            L("emph", "EMPHATIC-REFLEXIVE", reflexive="true"), L("state", "ADJ"),
            M("stop", "SPEECH-STOP"), M("close", "CLOSE-QUOTE"),
        ),
        "quoted",
    ),
    (
        RECOVERY_RELATIVE,
        re.compile(
            rf"(?P<det>This|That|The) +(?P<subject>{_W}) +(?P<of>of) +(?P<domain>{_NOM}?) +"
            rf"(?P<strain>preyed|weighed|pressed) +(?P<on>upon|on) +"
            rf"(?P<health>{_POSSESSIVE} +(?:health|spirits|mind|strength))(?P<comma>,) +"
            rf"(?P<which>which) +(?P<had>had) +(?P<maybe>perhaps|surely|probably) +(?P<never>never) +"
            rf"(?P<fully>entirely|fully|completely) +(?P<recover>recovered|rebounded) +(?P<from>from) +"
            rf"(?P<shock>the +(?:first|last|initial) +{_W}) +(?P<who>{_SUBJECT}) +"
            rf"(?P<had2>had) +(?P<sustain>sustained|received|suffered|endured)(?P<stop>\.)",
        ),
        (
            L("det", "DET"), L("subject", "N", attested_reading="true"), L("of", "PREP"), P("domain", "NP"),
            L("strain", "V", vform="finite", lemma_in="prey|weigh|press"),
            L("on", "PREP"), P("health", "NP", proof_rule="np_poss"), M("comma", "COMMA"),
            L("which", "WH-PRONOUN"), L("had", "HAVE", vform="finite"),
            L("maybe", "ADV"), L("never", "ADV"), L("fully", "ADV"),
            L("recover", "V", vform="ed", subcat_member="intransitive"), L("from", "PREP"),
            P("shock", "NP", proof_rule="np_det_n"), P("who", "NP"),
            L("had2", "HAVE", vform="finite"),
            L("sustain", "V", vform="ed", subcat_member="transitive"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        PERCEIVED_REACTION,
        re.compile(
            rf"(?P<subject>you) +(?P<have>have) +(?P<read>read|heard|seen) +"
            rf"(?P<story>(?:this|that|the) +{_NOM}?)(?P<comma>,) +(?P<voc>{_DESTINATION})(?P<semi>;) +"
            rf"(?P<and>and) +(?P<do>do) +(?P<you>you) +(?P<not>not) +"
            rf"(?P<feel>feel|see|hear) +(?P<body>your +{_W}) +(?P<reaction>congeal|freeze|tremble|shake) +"
            rf"(?P<with>with) +(?P<feeling>horror|fear|dread|terror)(?P<comma2>,) +"
            rf"(?P<like>like) +(?P<that>that) +(?P<which>which) +"
            rf"(?P<even>even) +(?P<now>now) +(?P<react>curdles|freezes|shakes|chills) +"
            rf"(?P<mine>mine)(?P<question>\?)",
            re.I,
        ),
        (
            P("subject", "NP"), L("have", "HAVE", vform="finite"),
            S("read", "V", vform="ed", subcat_member="transitive"),
            P("story", "NP"), M("comma", "COMMA"), P("voc", "NP"), M("semi", "SEMICOLON"),
            L("and", "COORD"), L("do", "AUX", vform="finite"), P("you", "NP"),
            L("not", "NEG"), L("feel", "V", vform="base"), P("body", "NP", proof_rule="np_poss"),
            L("reaction", "V", vform="base", subcat_member="intransitive"), L("with", "PREP"),
            L("feeling", "N", attested_reading="true"), M("comma2", "COMMA"), L("like", "COMPARISON-PREP"),
            P("that", "NP"), L("which", "WH-PRONOUN"), L("even", "ADV"), L("now", "ADV"),
            L("react", "V", vform="finite", subcat_member="transitive"),
            S("mine", "PRONOUN", possessive="true"), M("question", "QMARK"),
        ),
        "finite",
    ),
    (
        POSSESSIVE_COORDINATION,
        re.compile(
            rf"(?P<measure>{_W}) +(?P<units>years|months|weeks|days) +(?P<before>before|earlier)(?P<comma>,) +"
            rf"(?P<subject>{_SUBJECT}) +(?P<be>was|were) +(?P<status>engaged|occupied) +"
            rf"(?P<in>in) +(?P<context>the +same +{_W}) +(?P<and>and) +(?P<had>had) +"
            rf"(?P<create>created|made|raised|summoned) +(?P<creature>a +{_W}) +(?P<whose>whose) +"
            rf"(?P<quality>{_W} +{_W}) +(?P<had2>had) +"
            rf"(?P<affect>desolated|wounded|troubled|broken|damaged) +(?P<part>{_POSSESSIVE} +{_W}) +"
            rf"(?P<and2>and) +(?P<fill>filled|suffused) +(?P<it>it) +(?P<time>forever|evermore|permanently) +"
            rf"(?P<with>with) +(?P<content>the +{_W} +{_W})(?P<stop>\.)",
        ),
        (
            L("measure", "NUM"), L("units", "N"), L("before", "ADV"), M("comma", "COMMA"),
            P("subject", "NP"), L("be", "COPULA", vform="finite"), L("status", "ADJ"),
            L("in", "PREP"), P("context", "NP"), L("and", "COORD"), L("had", "HAVE", vform="finite"),
            L("create", "V", vform="ed", subcat_member="transitive"),
            P("creature", "NP", proof_rule="np_det_n"), L("whose", "WH-REL-POSS"),
            P("quality", "NP", proof_rule="np_bare"), L("had2", "HAVE", vform="finite"),
            L("affect", "V", vform="ed", subcat_member="transitive"), P("part", "NP", proof_rule="np_poss"),
            L("and2", "COORD"), L("fill", "V", vform="ed", subcat_member="transitive"),
            P("it", "NP"), L("time", "ADV"), L("with", "PREP"),
            P("content", "NP", proof_rule="np_det_n"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        RECOGNITION_CONTEXT,
        re.compile(
            rf"(?P<subject>(?:My|Her|His|Their|The) +{_NOM}?) +(?P<be>was|were) +"
            rf"(?P<temporal>in the meantime|for the moment|at the time) +"
            rf"(?P<state>overjoyed|delighted|relieved|pleased) +(?P<and>and) +"
            rf"(?P<in>in) +(?P<d1>the) +(?P<context>{_W}) +(?P<of1>of) +(?P<activity>{_W}) +(?P<only>only) +"
            rf"(?P<see>recognized|recognised|noticed|discerned|detected) +(?P<in2>in) +"
            rf"(?P<d2>the) +(?P<evidence>{_W}) +(?P<of2>of) +(?P<person>{_POSSESSIVE} +{_W}) +"
            rf"(?P<d3>the) +(?P<theme>{_W}) +(?P<of3>of) +(?P<type>(?:a|an) +{_W})(?P<stop>\.)",
        ),
        (
            P("subject", "NP", simple_nominal_proof="true"), L("be", "COPULA", vform="finite"),
            L("temporal", "ADV"), L("state", "ADJ"), L("and", "COORD"), L("in", "PREP"),
            L("d1", "DET"), L("context", "N"), L("of1", "PREP"), P("activity", "NP"), L("only", "ADV"),
            L("see", "V", vform="finite", subcat_member="transitive"), L("in2", "PREP"),
            L("d2", "DET"), L("evidence", "N"), L("of2", "PREP"), P("person", "NP", proof_rule="np_poss"),
            L("d3", "DET"), L("theme", "N"), L("of3", "PREP"), P("type", "NP", proof_rule="np_det_n"),
            M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
    (
        DIALECT_CAUSE,
        re.compile(
            rf'(?P<open1>["“‘])(?P<ah>Ah)(?P<comma1>,) +(?P<there>there|here)(?P<comma2>,)'
            rf'(?P<close1>["”’]) +(?P<said>said|replied|answered) +(?P<speaker>{_DESTINATION})'
            rf'(?P<comma3>,) +(?P<open2>["“‘])(?P<that>that|this) +(?P<come>comed|came) +'
            rf'(?P<of>of) +(?P<spoil>sp[’\x27]iling|spoiling|breaking|burning) +(?P<object>{_NOM})(?P<stop>\.)(?P<close2>["”’])',
        ),
        (
            M("open1", "OPEN-QUOTE"), L("ah", "INTERJ"), M("comma1", "COMMA"),
            L("there", "ADV"), M("comma2", "COMMA"), M("close1", "CLOSE-QUOTE"),
            L("said", "V", vform="finite"), P("speaker", "NP"), M("comma3", "COMMA"),
            M("open2", "OPEN-QUOTE"), P("that", "NP"),
            L("come", "V", vform="finite", lemma_in="come", subcat_member="prepositional"),
            L("of", "PREP"), S("spoil", "V", vform="ing", subcat_member="transitive"),
            P("object", "NP"), M("stop", "SPEECH-STOP"), M("close2", "CLOSE-QUOTE"),
        ),
        "quoted",
    ),
    (
        NEGATIVE_REPRISE,
        re.compile(
            rf'(?P<open1>["“‘])(?P<no>No)(?P<comma1>,)(?P<close1>["”’]) +'
            rf'(?P<said>said|replied|answered) +(?P<speaker>(?:Dr\. +)?{_DESTINATION})(?P<comma2>,) +'
            rf'(?P<open2>["“‘])(?P<subject>I|You|He|She|It|We|They) +(?P<do>do|does|did)'
            rf'(?P<negative>n[’\x27]t)(?P<stop>\.)(?P<close2>["”’])',
        ),
        (
            M("open1", "OPEN-QUOTE"), S("no", "INTERJECTION", response_particle="true"),
            M("comma1", "COMMA"), M("close1", "CLOSE-QUOTE"),
            L("said", "V", vform="finite"), P("speaker", "NP"), M("comma2", "COMMA"),
            M("open2", "OPEN-QUOTE"), P("subject", "NP"), L("do", "AUX", vform="finite"),
            L("negative", "NEG", negation="true"), M("stop", "SPEECH-STOP"), M("close2", "CLOSE-QUOTE"),
        ),
        "quoted",
    ),
    (
        ADMISSION,
        re.compile(
            rf"(?P<here>Here|There|Then) +(?P<subject>(?:Mr\.|Mrs\.|Dr\.) +{_DESTINATION}) +"
            rf"(?P<motion>dismounted|alighted|stopped|paused)(?P<comma>,) +(?P<and>and) +"
            rf"(?P<taking>taking|bringing|leading) +(?P<object>me|us|him|her|them) +"
            rf"(?P<along>along) +(?P<with>with) +(?P<companion>him|her)(?P<comma2>,) +"
            rf"(?P<was>was) +(?P<admit>admitted|welcomed|ushered) +"
            rf"(?P<at>at) +(?P<cue>a +(?:word|nod|sign|gesture)) +(?P<into>into) +"
            rf"(?P<destination>the +{_NOM})(?P<stop>\.)",
        ),
        (
            L("here", "ADV"), P("subject", "NP"),
            L("motion", "V", vform="finite", subcat_member="intransitive"),
            M("comma", "COMMA"), L("and", "COORD"),
            L("taking", "V", vform="ing", subcat_member="transitive"),
            P("object", "NP"), L("along", "ADV"), L("with", "PREP"), P("companion", "NP"),
            M("comma2", "COMMA"), L("was", "AUX-BE", vform="finite"),
            L("admit", "V", vform="ed", subcat_member="transitive"), L("at", "PREP"),
            P("cue", "NP", proof_rule="np_det_n"), L("into", "PREP"),
            P("destination", "NP", simple_nominal_proof="true"), M("stop", "SPEECH-STOP"),
        ),
        "finite",
    ),
)


def _guard(root, pattern, layout, kind):
    build = _planner(root, pattern, layout, kind)

    def plan(text, parts):
        m = pattern.fullmatch(text)
        if m is None:
            return None
        if root == OBJECT_RELATIVE:
            singular = m["alls"] in ("everyone", "everybody")
            if (m["have"] == "has") != singular:
                return None
        if root == PARALLEL_INVERSION:
            if m["again"].casefold() != m["again2"]:
                return None
            for subject, aux in ((m["subject"], m["do"]), (m["subject2"], m["do2"])):
                if aux != "did" and (aux == "does") != (subject in ("he", "she", "it")):
                    return None
            if not any(c.get("function") == "independent_clause"
                       and c["start"] == m.start("again2") for c in parts):
                return None
        if root == NEGATIVE_REPRISE and m["do"] != "did":
            if (m["do"] == "does") != (m["subject"].lower() in ("he", "she", "it")):
                return None
        if root == PERCEIVED_REACTION and not any(
                c.get("function") == "coordinate_clause" and c["start"] == m.start("and") for c in parts):
            return None
        if root == REPORT_COMMAND:
            quotes = [c for c in parts if c.get("function") == "direct_speech"]
            reports = [c for c in parts if c.get("function") == "reporting_clause"]
            acts = [c for c in parts if c.get("function") == "spoken_clause_candidate"]
            if (len(quotes) != 1 or len(reports) != 1
                    or quotes[0].get("governor") != reports[0]["id"]
                    or (reports[0]["start"], reports[0]["end"]) != (0, m.end("report"))
                    or [(c["start"], c["end"]) for c in acts
                        if c.get("governor") == quotes[0]["id"]]
                    != [(m.start("voc"), m.end("excl")), (m.start("before"), m.end("stop"))]):
                return None
        specs = build(text, parts)
        if specs is not None and root == PERCEPTION_GESTURE:
            start, stop = m.span("affect")
            phrase = re.fullmatch(rf"(the) +({_W}) +(of) +({_W})", text[start:stop])
            if phrase:
                i = next(i for i, spec in enumerate(specs) if spec[1:3] == (start, stop))
                specs[i:i + 1] = [(category, start + phrase.start(g), start + phrase.end(g),
                                    "lexical-alternatives", {})
                                   for g, category in enumerate(("DET", "N", "PREP", "N"), 1)]
        if specs is not None and root == PARALLEL_INVERSION:
            start, stop = m.span("fate")
            coordinated = re.fullmatch(rf"({_NOM}?) +(and) +({_NOM})", text[start:stop])
            if coordinated:
                i = next(i for i, spec in enumerate(specs) if spec[1:3] == (start, stop))
                specs[i:i + 1] = [(category, start + coordinated.start(g),
                                    start + coordinated.end(g), kind, {})
                                   for g, category, kind in ((1, "NP", "phrase"),
                                                             (2, "COORD", "lexical-alternatives"),
                                                             (3, "NP", "phrase"))]
        return specs

    return plan


NARRATIVE_PLANS = tuple((root, _guard(root, pattern, slots, kind))
                        for root, pattern, slots, kind in PLANS if kind != "quoted")
SPOKEN_PLANS = tuple((root, _guard(root, pattern, slots, kind))
                     for root, pattern, slots, kind in PLANS if kind == "quoted")
COUNTS = {**dict.fromkeys((root for root, *_ in PLANS), 1),
          PARALLEL_INVERSION: 2, PERCEIVED_REACTION: 2}
