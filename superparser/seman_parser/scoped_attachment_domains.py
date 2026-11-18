"""Source gates for independently proved attachment domains.

A gate specifies only the original spans to prove. The lexical lattice and
main grammar still prove words and bounded phrases, then the structural
grammar builds and ranks a typed derivation. The gates do not use document
names, indices, or a table of attested sentences.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re

from .dialogue import quotation_boundaries
from .scoped_transfer_clauses import _matrix

W = r"[a-z][a-z’'\-]*"
NOMINAL = rf"{W}(?: +{W}){{0,6}}"
NAME = r"[A-Z][a-z]+(?: +[A-Z][a-z]+)?"
PRON = r"I|we|you|they|he|she|it"
POSSESSIVE = r"my|our|your|their|his|her|its"
OBJ = r"me|us|you|them|him|her|it"


@dataclass(frozen=True)
class Span:
    pattern: str
    category: str
    kind: str
    features: dict[str, str]
    label: str | None = None


def lx(pattern, category, *, alternatives=False, **features):
    kind = "lexical-alternatives" if alternatives else "lexical"
    return Span(pattern, category, kind, {"attested_reading": "true", **features})


def v(pattern, form, frame, *lemmas, **features):
    if lemmas:
        features["lemma_in"] = "|".join(lemmas)
    return Span(pattern, "V", "lexical-alternatives", {
        "attested_reading": "true", "vform": form, "subcat_member": frame, **features,
    })


def scoped(pattern, category, **features):
    return Span(pattern, category, "scoped-lexical", features)


def phrase(pattern, category="NP", rule=None, **features):
    if rule:
        features["proof_rule"] = rule
    return Span(pattern, category, "phrase", features)


def subject(pattern=PRON):
    return Span(pattern, "NP", "subject-phrase", {})


def name(pattern=NAME):
    return Span(pattern, "NP", "proper-phrase", {})


def labelled(label, span):
    return replace(span, label=label)


def mark(text, category):
    return Span(re.escape(text), category, "source-punctuation", {})


COMMA = mark(",", "COMMA")
STOP = mark(".", "SPEECH-STOP")
SEMI = mark(";", "SEMICOLON")
QMARK = mark("?", "QMARK")
OPEN = Span(r'["“‘]', "OPEN-QUOTE", "source-punctuation", {})
CLOSE = Span(r'["”’]', "CLOSE-QUOTE", "source-punctuation", {})
AND = lx("and", "COORD", lemma_in="and")
BUT = lx("but", "COORD", lemma_in="but")
HAD = lx("had", "HAVE", vform="finite")
ASPECT_HAVE = lx("have|has|had", "HAVE", alternatives=True, vform="finite")
PAST_BE = lx("was|were", "AUX-BE", alternatives=True, vform="finite")
COP_PAST = lx("was|were", "COPULA", alternatives=True, vform="finite")
POS = lx(POSSESSIVE, "POSS", anaphor="true")
TO = lx("to", "TO")
OF = lx("of", "PREP", lemma_in="of")
NOT = lx("not", "NEG")


def _source_evidence(text, parts, specs, *, speech):
    if speech:
        quoted = [s for s in specs if s[0] in ("OPEN-QUOTE", "CLOSE-QUOTE")]
        if len(quoted) % 2 or not quoted:
            return False
        if [(a, b, "open" if c == "OPEN-QUOTE" else "close") for c, a, b, _, _ in quoted] != [
            (q.start, q.end, q.side) for q in quotation_boundaries(text)
        ]:
            return False
        expected = {(a[1], b[2]) for a, b in zip(quoted[::2], quoted[1::2], strict=True)}
        return expected == {(p["start"], p["end"]) for p in parts
                            if p.get("function") == "direct_speech"}
    separators = [s for s in specs if s[0] == "SEMICOLON"]
    if not separators:
        return _matrix(text, parts)
    if len(separators) != 1 or any(p.get("function") == "direct_speech" for p in parts):
        return False
    _, a, b, _, _ = separators[0]
    start = b + len(text[b:]) - len(text[b:].lstrip())
    return (
        any(p.get("function") == "matrix_clause" and (p["start"], p["end"]) == (0, a)
            for p in parts)
        and any(p.get("function") in ("independent_clause", "coordinate_clause")
                and (p["start"], p["end"]) == (start, len(text)) for p in parts)
    )


NARRATIVE = []
SPOKEN = []
SEQUENCES = []
COUNTS = {}


def family(rule, count, *layout, speech=False, sequence=False):
    """A literal space separates constituents, not lexemes inside phrases."""
    spans = tuple(piece for piece in layout if isinstance(piece, Span))
    regex = re.compile("".join(
        f"(?P<{piece.label}>{piece.pattern})" if isinstance(piece, Span) and piece.label
        else f"({piece.pattern})" if isinstance(piece, Span) else piece
        for piece in layout
    ))

    if regex.groups != len(spans):
        raise ValueError(f"Use noncapturing groups within source spans for {rule}")
    if rule in COUNTS or (sequence and not speech):
        raise ValueError(f"Duplicate or invalid attachment family {rule}")

    def plan(text, parts):
        match = regex.fullmatch(text)
        if match is None:
            return None
        specs = [(piece.category, *match.span(i), piece.kind, piece.features)
                 for i, piece in enumerate(spans, 1)]
        return specs if _source_evidence(text, parts, specs, speech=speech) else None

    (SEQUENCES if sequence else SPOKEN if speech else NARRATIVE).append((rule, plan))
    COUNTS[rule] = count


SENSATION = "structural_sensation_come_across_with_time"
family(SENSATION, 1,
       lx("A|An", "DET"), " ", lx("tingling|strange|sudden|vague|faint|sharp", "ADJ"), " ",
       lx("long-lost|forgotten|familiar|unfamiliar", "ADJ"), " ",
       lx("sense|feeling|sensation", "N"), " ", OF, " ",
       phrase(r"pleasure|fear|dread|relief|wonder|joy", rule="np_bare"), " ",
       lx("often|sometimes|frequently|occasionally", "ADV"), " ",
       v("came", "finite", "prepositional", "come"), " ",
       lx("across|over", "PREP"), " ", phrase(OBJ, rule="np_indef_pron"), " ",
       lx("during", "PREP"), " ", phrase(rf"(?:this|that|the|our) +{NOMINAL}"), STOP)

WEATHER = "structural_contrastive_persistence_and_passive_state"
family(WEATHER, 3,
       subject(r"The +(?:thunder|storm|wind|rain|snow)"), " ",
       v("ceased|stopped|subsided", "finite", "intransitive"), SEMI, " ", BUT, " ",
       subject(r"the +(?:thunder|storm|wind|rain|snow)"), " ", lx("still", "ADV"), " ",
       v("continued|persisted|fell|blew", "finite", "intransitive"), COMMA, " ", AND, " ",
       subject(r"the +(?:scene|valley|town|street|village|coast)"), " ", PAST_BE, " ",
       v("enveloped|shrouded|wrapped|covered", "ed", "transitive"), " ",
       lx("in", "PREP"), " ", lx("a|an", "DET"), " ", lx(W, "ADJ"), " ",
       lx("darkness|mist|fog|smoke|gloom|haze", "N"), STOP)

TRAVEL_RELATIVE = "structural_shared_travel_with_goal_supplementary_relative"
family(TRAVEL_RELATIVE, 2,
       subject(r"We|They|I|He|She"), " ", v("left|quit", "finite", "transitive"), " ",
       name(), " ", lx("with", "PREP"), " ", phrase("regret|relief|sorrow", rule="np_bare"), " ",
       AND, " ", v("proceeded|travelled|went|walked", "finite", "prepositional"), " ",
       lx("to", "PREP"), " ", name(), COMMA, " ", lx("which", "WH-PRONOUN"), " ", COP_PAST, " ",
       POS, " ", lx("next|last|first|usual", "ADJ"), " ", lx("place|point|station", "N"), " ",
       OF, " ", phrase("rest|departure|shelter|meeting", rule="np_bare"), STOP)

HAND_CIRCUMSTANCE = "structural_fronted_possession_circumstance_and_address"
family(HAND_CIRCUMSTANCE, 1,
       lx("Then|Now", "ADV"), COMMA, " ", lx("with", "PREP"), " ",
       phrase(r"a +(?:pistol|knife|candle|torch|letter|book|lantern)", rule="np_det_n"), " ",
       lx("in", "PREP"), " ", phrase(rf"(?:(?:{POSSESSIVE}) +(?:(?:right|left) +)?|(?:each|either) +)hand"),
       COMMA, " ", subject(), " ",
       v("addressed|approached|greeted|confronted", "finite", "transitive"), " ",
       phrase(OBJ, rule="np_indef_pron"), STOP)

LIKELIHOOD = "structural_nominal_fragment_with_epistemic_likelihood"
family(LIKELIHOOD, 0,
       phrase(r"(?:A|An|The) +(?:knife|bullet|arrow|needle|splinter|wound)", rule="np_det_n"), " ",
       lx("in", "PREP"), " ", phrase(rf"(?:{POSSESSIVE}) +(?:back|arm|leg|shoulder|foot|side)", rule="np_poss"),
       " ", scoped("as like as not|as likely as not", "STANCE", epistemic="true"), STOP)

GIVE_CAUSATIVE = "structural_interposed_time_ditransitive_and_causative_relative"
family(GIVE_CAUSATIVE, 3,
       lx("And|But", "COORD"), " ", subject(), " ", v("gave", "finite", "ditransitive", "give"),
       " ", phrase(OBJ, rule="np_indef_pron"), COMMA, " ", lx("as|while", "CONJ"), " ", subject(),
       " ", v("spoke|talked|laughed|smiled|worked", "finite", "intransitive"), COMMA, " ",
       phrase(r"a +(?:wrench|twist|push|shove|pull|tug|shake|jerk)", rule="np_det_n"), " ",
       lx("that|which", "WH-PRONOUN"), " ",
       scoped("made", "V", vform="finite", subcat="causative"), " ",
       phrase(OBJ, rule="np_indef_pron"), " ",
       v("cry|call|yell|laugh|jump|spin", "base", "intransitive"), " ",
       lx("out|round|up", "PARTICLE"), STOP)

STANCE_COORD = "structural_transitive_coordination_across_epistemic_incise"
family(STANCE_COORD, 3,
       subject(r"I|We|You|They|He|She"), " ",
       v("petted|praised|cherished|indulged|admired|encouraged", "finite", "transitive"), " ",
       phrase(OBJ, rule="np_indef_pron"), COMMA, " ", lx("as", "CONJ"), " ", subject("I|we"),
       " ", lx("may|might|could", "MODAL"), " ", v("say", "base", "clausal", "say"),
       COMMA, " ", AND, " ", v("made", "finite", "transitive", "make"), " ",
       lx("the", "DET"), " ", scoped("most|best", "N", maximal_extent="true"), " ", OF, " ",
       phrase(OBJ, rule="np_indef_pron"), STOP)

DOUBLE_DEGREE = "structural_shared_standard_of_two_adjectival_comparatives"
family(DOUBLE_DEGREE, 2,
       lx("When|As|After", "CONJ"),
       " ", phrase(rf"(?:{PRON}) +(?:accosted|greeted|met|approached|addressed) +(?:{OBJ})",
                   "CLAUSE", "clause_np_vp", finite_statement_proof="true"),
       COMMA, " ", phrase(rf"(?:{POSSESSIVE}) +(?:manner|bearing|demeanour|demeanor|behaviour|behavior)",
                         rule="np_poss"),
       " ", COP_PAST, " ", scoped("something|somewhat", "DEGREE", mitigator="true"), " ",
       lx("more|less", "DEGREE"), " ", lx(W, "ADJ"), COMMA, " ", AND, " ",
       scoped("something|somewhat", "DEGREE", mitigator="true"), " ",
       lx("more|less", "DEGREE"), " ", lx(W, "ADJ"), COMMA, " ",
       lx("than", "PREP", comparative="true"), " ",
       scoped("of yore|of old|before", "ADV", past_standard="true"), STOP)

TOPICAL_QUESTION = "structural_vocative_wh_object_modal_with_nominal_topic"
family(TOPICAL_QUESTION, 1,
       name(), COMMA, " ", lx("what|which", "WH-NOM"), " ",
       lx("comment|remark|observation|statement|pronouncement", "N"), " ",
       lx("can|could|may|might|should", "MODAL"), " ", subject(), " ",
       v("make|offer|give", "base", "transitive"), " ",
       lx("on|about", "PREP"), " ", lx("the", "DET"), " ", lx(W, "ADJ"), " ",
       lx("extinction|loss|end|departure|destruction|death|passing", "N"), " ", OF, " ",
       lx("this|that", "DET"), " ", lx(W, "ADJ"), " ", lx(W, "N"), QMARK)

PARALLEL_PERFECT = "structural_parallel_perfects_with_nominal_scope_before_semicolon"
family(PARALLEL_PERFECT, 2,
       subject(r"I|We|You|They|He|She"), " ", ASPECT_HAVE, " ",
       v("lost|abandoned|forgotten|missed", "ed", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:hopes|dreams|expectations|thoughts)", rule="np_poss"),
       " ", OF, " ", phrase(W, rule="np_bare"), " ", AND, " ", phrase(W, rule="np_bare"),
       SEMI, " ", subject(), " ", ASPECT_HAVE, " ",
       v("lost|abandoned|forgotten|missed", "ed", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +{W}", rule="np_poss"), STOP)

DIPPING = "structural_subject_controlled_participial_and_frequency_supplement"
family(DIPPING, 2,
       lx("The", "DET"), " ", lx(r"[A-Z][A-Z]+|ship|boat|vessel|schooner|yacht|brig", "N"),
       " ", v("rolled|rocked|pitched|swayed", "finite", "intransitive"), " ",
       lx("steadily|gently|heavily|slowly|rhythmically", "ADV"), COMMA, " ",
       v("dipping|lowering|lifting|raising", "ing", "transitive"), " ",
       phrase(rf"(?:her|its) +(?:bowsprit|bow|prow|stern|mast)", rule="np_poss"), " ",
       scoped("now and then|from time to time|every so often", "ADV", intermittent="true"), " ",
       lx("with", "PREP"), " ", phrase(rf"a +(?:whiff|gust|cloud|burst|jet|shower) +of +{W}", rule="np_det_n_of"),
       STOP)

LONG_SECRET = "structural_modal_negated_copula_with_temporal_duration"
family(LONG_SECRET, 1,
       lx("The", "DET"), " ", lx("situation|state|condition|truth|nature|course", "N"), " ", OF, " ",
       phrase(r"affairs|events|things|matters|business", rule="np_bare"), " ", lx("in", "PREP"), " ",
       phrase(r"the +(?:[A-Z][a-z]+ +)?(?:family|household|village|town|company)"), " ",
       lx("could|would|might|should|will|can", "MODAL"), " ", NOT, " ",
       lx("be", "COPULA", vform="base"), " ", lx("long", "ADV"), " ",
       phrase(r"a +(?:secret|mystery|surprise|problem|burden)", rule="np_det_n"), STOP)

PRAISE_GENITIVE = "structural_manner_praise_with_embedded_genitive_content"
family(PRAISE_GENITIVE, 1,
       name(r"(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+|[A-Z][a-z]+"), " ",
       v("spoke|talked|answered|replied", "finite", "intransitive"), " ",
       lx("with", "PREP"), " ", lx("affectionate|warm|genuine|great|sincere|unreserved", "ADJ"), " ",
       lx("praise|admiration|approval|appreciation", "N"), " ", OF, " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:sister|brother|mother|father|friend|daughter|son|pupil|teacher)[’']s +{W}",
              rule="np_genitive"), STOP)

RESCUE_SERIES = "structural_care_coordination_with_errand_and_terminal_state"
family(RESCUE_SERIES, 3,
       subject(r"They|We|You|He|She"), " ", v("put|placed|laid", "finite", "transitive"),
       " ", phrase(OBJ, rule="np_indef_pron"), " ", lx("into|onto|on", "PREP"), " ",
       phrase(r"a +(?:bed|cot|chair|sofa|bench|couch)", rule="np_det_n"), " ", AND, " ",
       v("rubbed|warmed|covered|examined|dried", "finite", "transitive"), " ",
       phrase(OBJ, rule="np_indef_pron"), COMMA, " ", AND, " ", name(), " ",
       v("went|rode|walked|ran|hurried", "finite", "prepositional"), " ", lx("to", "PREP"), " ",
       phrase(r"the +(?:town|village|city|hospital|house|farm)", rule="np_det_n"), " ",
       lx("for", "PREP"), " ", phrase("an? +(?:apothecary|doctor|surgeon|nurse|physician|midwife)", rule="np_det_n"),
       COMMA, " ", BUT, " ", phrase("life|hope", rule="np_bare"), " ", COP_PAST, " ",
       lx("quite|already|completely|almost", "DEGREE"), " ", lx("gone|extinct|lost", "ADJ"), STOP)

ACCEPTANCE = "structural_passive_certainty_then_time_framed_joining"
family(ACCEPTANCE, 2,
       subject(r"The +(?:invitation|offer|proposal|request|suggestion|plan)"), " ", PAST_BE,
       " ", v("accepted|declined|approved|rejected", "ed", "transitive"), " ",
       scoped("of course|naturally|certainly", "STANCE", certainty="true"), COMMA, " ", AND,
       " ", lx("at", "PREP"), " ", phrase(r"a +(?:proper|suitable|reasonable|late|good) +hour", rule="np_det_n"),
       " ", subject(), " ", v("joined|met|greeted", "finite", "transitive"), " ",
       phrase(r"the +(?:party|guests|company|group|visitors|family)", rule="np_det_n"), " ",
       lx("in", "PREP"), " ",
       phrase(r"(?:(?:Mr\.|Mrs\.|Dr\.|[A-Z][a-z]+) +)?[A-Z][a-z]+[’']s +(?:drawing-room|room|hall|parlour|study|garden)",
              rule="np_genitive"), STOP)

RESCUED_RESTORED = "dialogue_structural_rescue_source_and_perfect_restoration_goal"
family(RESCUED_RESTORED, 2,
       OPEN, lx("And|But", "COORD"), " ", lx("yet|still", "ADV"), " ", subject(), " ",
       v("rescued|saved|delivered|freed", "finite", "transitive"), " ", phrase(OBJ, rule="np_indef_pron"),
       " ", lx("from", "PREP"), " ", lx("a", "DET"), " ", lx(W, "ADJ"), " ", AND,
       " ", lx(W, "ADJ"), " ", lx("situation|place|position|trap|predicament", "N"), SEMI, " ",
       subject(), " ", ASPECT_HAVE, " ", lx("[a-z]+ly", "ADV"), " ",
       v("restored|returned|brought", "ed", "transitive"), " ", phrase(OBJ, rule="np_indef_pron"),
       " ", lx("to", "PREP"), " ", phrase("life|health|safety|liberty", rule="np_bare"), STOP, CLOSE,
       speech=True, sequence=True)

PROGRESSIVE_WH = "dialogue_structural_progressive_question_with_stranded_about_and_vocative"
family(PROGRESSIVE_WH, 1,
       OPEN, lx("What|Who", "WH-NOM"), " ", lx("are|were", "AUX-BE", alternatives=True, vform="finite"),
       " ", subject(r"you|we|they"), " ", v("talking|speaking|thinking|writing|arguing|asking", "ing", "prepositional"),
       " ", lx("about", "PREP"), COMMA, " ", name(), QMARK, CLOSE, " ",
       v("said|asked|cried|replied", "finite", "clausal", "say", "ask", "cry", "reply"), " ",
       scoped("Miss|Master|Doctor|Captain", "TITLE", honorific="true"), " ", name(r"[A-Z][a-z]+"),
       STOP, speech=True)

CLOCK_DAY = "structural_clock_predication_with_day_anchor_and_when_clause"
family(CLOCK_DAY, 2,
       scoped("It", "EXPL", temporal_expletive="true"), " ", COP_PAST, " ",
       lx("nearly|almost|about", "DEGREE"), " ", lx("dinner-time|dinnertime|lunchtime|breakfast-time|midnight|noon", "N"),
       " ", scoped("next day|the next day|the following day|the previous day", "ADV", relative_day="true"),
       " ", lx("when", "CONJ"), " ", subject(), " ",
       v("appeared|stood|passed|arrived|reported", "finite", "prepositional"), " ",
       lx("before|beside|near", "PREP"), " ", phrase(rf"(?:{POSSESSIVE}) +{W}", rule="np_poss"), STOP)

AFTER_CESSATION = "structural_temporal_perfect_incise_and_subject_controlled_looking"
family(AFTER_CESSATION, 2,
       subject(r"He|She|I|They|We|You"), " ", v("stood|sat|waited|remained|stayed", "finite", "intransitive"),
       COMMA, " ", lx("long|shortly", "ADV"), " ", lx("after|before", "CONJ"), " ", subject(), " ",
       HAD, " ", v("ceased|begun|started|continued", "ed", "subject_control"), " ", TO, " ",
       v("read|write|speak|sing|talk|work", "base", "intransitive"), COMMA, " ",
       lx("still", "ADV"), " ", v("looking|staring|gazing|peering|watching", "ing", "prepositional"),
       " ", lx("at|towards|toward", "PREP"), " ", phrase(OBJ, rule="np_indef_pron"), STOP)

LOOK_BUT = "structural_temporal_subordinate_before_shared_subject_negative_coordination"
family(LOOK_BUT, 3,
       subject(r"He|She|I|They|We|You"), " ", v("looked|gazed|stared|glanced", "finite", "prepositional"),
       " ", lx("at|towards|toward", "PREP"), " ", phrase(OBJ, rule="np_indef_pron"), " ",
       lx("[a-z]+ly", "ADV"), " ", lx("as|while|when", "CONJ"), " ", subject(), " ",
       v("entered|arrived|approached|spoke|waited|sat", "finite", "intransitive"), COMMA, " ", BUT, " ",
       v("made|gave|showed", "finite", "transitive"), " ", lx("no", "DET"), " ",
       lx("sign|gesture|display|mark|token|trace", "N"), " ", OF, " ",
       phrase(r"recognition|surprise|thanks|approval|regret|sympathy|concern", rule="np_bare"), " ",
       scoped("whatever|whatsoever", "DEGREE", minimizer="true"), STOP)

EXISTENTIAL_TOSS = "dialogue_structural_existential_report_with_gestural_supplement"
family(EXISTENTIAL_TOSS, 1,
       OPEN, lx("There", "EXPL"), lx("[’']s", "COPULA"), " ",
       phrase(r"a +(?:friend|help|visitor|gentleman|lady|sailor|stranger|coach)", rule="np_det_n"),
       mark("!", "SPEECH-STOP"), CLOSE, " ",
       v("murmured|whispered|said|cried|exclaimed", "finite", "clausal"), " ",
       name(r"(?:Mr\.|Mrs\.|Dr\.) +[A-Z][a-z]+|[A-Z][a-z]+"), COMMA, " ",
       lx("with", "PREP"), " ", lx("a", "DET"), " ", lx(W, "ADJ"), " ",
       lx("toss|shake|nod|turn|bow|tilt", "N"), " ", OF, " ", phrase(rf"(?:{POSSESSIVE}) +head", rule="np_poss"),
       STOP, speech=True, sequence=True)

CONTRASTIVE_INF = "structural_paired_infinitival_gap_modifiers_on_quantified_objects"
family(CONTRASTIVE_INF, 1,
       subject(r"They|We|He|She|I|You"), " ", v("saw|found|discovered|noticed|encountered", "finite", "transitive"),
       " ", scoped("much|little|something", "QUANT-NOM", quantificational="true"), " ", TO, " ",
       v("interest|impress|alarm|persuade|encourage|please", "base", "transitive"),
       COMMA, " ", BUT, " ", lx("nothing|something", "PRONOUN"), " ", TO, " ",
       v("justify|warrant|arouse|occasion|encourage", "base", "transitive"),
       " ", phrase("inquiry|alarm|suspicion|a +search|a +visit|concern|reproach"), STOP)

PASSIVE_RESULT = "structural_passive_resultative_between_locative_events"
family(PASSIVE_RESULT, 3,
       phrase(r"[A-Z][a-z]+[’']s +(?:voice|cry|call|shout|laughter|scream|song)", rule="np_genitive"),
       " ", PAST_BE, " ", v("heard|recognized|noticed", "ed", "transitive"), " ",
       lx("in|from", "PREP"), " ", phrase(r"the +(?:vestibule|hall|room|garden|passage|corridor)", rule="np_det_n"),
       SEMI, " ", subject(r"the +(?:door|window|gate|shutters|doors|windows|gates)"), " ", PAST_BE, " ",
       v("thrown|pushed|forced|pulled|kicked", "ed", "transitive"), " ", lx("open|shut|closed", "ADJ"),
       COMMA, " ", AND, " ", subject(), " ", v("ran|walked|rushed|stepped|came|went", "finite", "prepositional"),
       " ", lx("into|through|out of", "PREP"), " ", phrase(r"the +(?:room|hall|house|garden|passage|street)", rule="np_det_n"),
       STOP)

DURATION_PASSIVE = "structural_preposed_reduced_passive_duration_and_main_passive_cause"
family(DURATION_PASSIVE, 1,
       lx("After", "PREP"), " ", phrase(r"a +(?:week|day|month|year|night|morning|afternoon)", rule="np_det_n"),
       " ", v("spent|passed|consumed", "ed", "transitive"), " ", lx("in", "PREP"), " ",
       lx("professions|displays|expressions|works|songs|exercises|discussions", "N"), " ", OF, " ",
       phrase(r"love|affection|friendship|hope|pride|fury|joy|grief|approval|doubt|faith", rule="np_bare"),
       " ", AND, " ", lx("schemes|plans|dreams|visions|promises|hopes", "N"), " ", OF, " ",
       phrase(r"felicity|happiness|success|glory|adventure|travel|splendour|victory|peace", rule="np_bare"),
       COMMA, " ", name(r"(?:Mr\.|Mrs\.|Dr\.) +[A-Z][a-z]+|[A-Z][a-z]+"), " ",
       PAST_BE, " ", v("called|summoned|taken|parted|removed", "ed", "transitive"), " ",
       lx("from", "PREP"), " ", POS, " ", lx("amiable|dear|beloved|kind|gentle|faithful", "ADJ"), " ", name(r"[A-Z][a-z]+"),
       " ", lx("by", "PREP"), " ", lx("the", "DET"), " ", lx("arrival|approach|return|coming|passage", "N"),
       " ", OF, " ", name(), STOP)

INVERTED_REQUEST = "structural_in_vain_inversion_with_control_and_shared_offer"
family(INVERTED_REQUEST, 2,
       scoped("In vain", "ADV", futile="true"), " ", lx("did", "AUX"), " ", subject(), " ",
       v("entreat|urge|ask|beg|invite", "base", "object_control"), " ",
       phrase(OBJ, rule="np_indef_pron"), " ", TO, " ",
       v("stand up|dance|walk|sit", "base", "intransitive"), " ",
       lx("with", "PREP"), " ", scoped("somebody else|someone else|anyone else", "PRONOUN", alternative="true"),
       COMMA, " ", AND, " ", v("offer|promise|volunteer", "base", "subject_control"),
       " ", TO, " ", v("introduce|present", "base", "transitive"), " ",
       phrase(OBJ, rule="np_indef_pron"), " ", lx("to", "PREP"), " ",
       lx("any|a", "DET"), " ", lx("young|old|other", "ADJ"), " ", lx("lady|gentleman|person|woman|man", "N"),
       " ", lx("in", "PREP"), " ", phrase(r"the +(?:room|hall|garden|house)", rule="np_det_n"), STOP)

REPORT_INTRO = v("said|asked|replied|answered|whispered|murmured|cried|added|complained|gasped|exclaimed",
                 "finite", "clausal")
DEMONSTRATIVE = scoped("That|This|that|this", "DEMONSTRATIVE-PRONOUN", deictic="true")
OH = scoped("Oh|Ah", "INTERJECTION", exclamative="true")
EXCLSTOP = mark("!", "SPEECH-STOP")
COP_PRESENT = lx("is|are|am", "COPULA", alternatives=True, vform="finite")
BE_BASE = lx("be", "COPULA", vform="base")
BEEN = lx("been", "COPULA", vform="ed")
SEP_TAG = (COMMA, CLOSE, " ")
RESTART = (COMMA, " ", OPEN)

DIALECT_PERMISSION = "dialogue_structural_negative_dialect_prospective_permission_with_address"
family(DIALECT_PERMISSION, 1,
       OPEN, subject(r"You|We|They|He|She|I"), " ",
       scoped("ain['’]t", "AUX-BE", negation="true", vform="finite"), " ",
       scoped("a-going|going", "PROSPECTIVE", prospective="true"), " ", TO, " ",
       scoped("let|allow", "V", vform="base", subcat="permission"), " ",
       phrase(OBJ, rule="np_indef_pron"), " ", lx("inside|outside|in|out|aboard|ashore", "ADV"),
       COMMA, " ", scoped(r"cap['’]n|captain|sir|mate", "VOCATIVE", address="true"), QMARK, CLOSE, " ",
       REPORT_INTRO, " ", lx("Long|Tall|Short|Young|Old", "ADJ"), " ", name(r"[A-Z][a-z]+"), STOP, speech=True)

FORGIVE_TAG = "dialogue_structural_reported_vocative_imperative_with_negative_modal_tag"
family(FORGIVE_TAG, 3,
       OPEN, name(), *SEP_TAG, REPORT_INTRO,
       " ", phrase(r"the +(?:squire|captain|doctor|officer|teacher|sailor|man|woman|girl|boy)", rule="np_det_n"),
       *RESTART, v("say|tell", "base", "clausal"), " ", subject("you"), " ",
       v("forgive|pardon|believe|trust|remember|understand", "base", "transitive"), " ",
       phrase(OBJ, rule="np_indef_pron"), COMMA, " ",
       scoped("wo", "MODAL", contracted_negative_stem="true"),
       scoped(r"n['’]t", "NEG", negation="true"), " ", subject("you"), QMARK, CLOSE,
       speech=True, sequence=True)

STAND_BY = "dialogue_structural_reported_vocative_two_coordinated_imperatives"
family(STAND_BY, 2,
       OPEN, name(), *SEP_TAG, subject(), " ", REPORT_INTRO,
       *RESTART, v("take|keep|hold|grab|watch", "base", "transitive"), " ", DEMONSTRATIVE, COMMA, " ", AND, " ",
       scoped("stand by|look out|watch out", "V", vform="base", subcat="prepositional"), " ",
       lx("for", "PREP"), " ", phrase(r"trouble|danger|help|orders|news|company", rule="np_bare"), STOP, CLOSE,
       speech=True, sequence=True)

THAT_SUPPOSE = "dialogue_structural_deictic_partitive_with_epistemic_incise"
family(THAT_SUPPOSE, 2,
       OPEN, lx("And|But", "COORD"), " ", DEMONSTRATIVE, " ", subject("I|we"), " ",
       v("suppose|think|believe|imagine|assume", "base", "clausal"), " ", COP_PRESENT, " ",
       lx("one|two|three", "NUM"), " ", OF,
       " ", phrase(rf"(?:{POSSESSIVE}) +(?:sisters|brothers|friends|children|relatives|cousins)", rule="np_poss"),
       STOP, CLOSE, speech=True, sequence=True)

GOOD_WORK = "dialogue_structural_split_modal_copula_and_present_perfect_copula"
family(GOOD_WORK, 2,
       OPEN, subject(r"It|He|She|They|You"), " ", scoped("ought", "MODAL", vform="finite", modal="true"),
       " ", TO, " ", BE_BASE, " ", lx("good|old|useful|strong|beautiful|true|clear|worthy", "ADJ"),
       *SEP_TAG, subject(), " ", REPORT_INTRO, *RESTART,
       subject("it|he|she|they|you"), " ", ASPECT_HAVE, " ", BEEN, " ",
       lx("the", "DET"), " ", lx("work|achievement|product|result|effort", "N"), " ", OF, " ",
       phrase(r"(?:many|several|two|three|four) +(?:generations|people|hands|artists|workers|families|builders)"),
       STOP, CLOSE, speech=True, sequence=True)

REPORTED_DEICTIC = "dialogue_structural_reported_exclamative_demonstrative_clause"
family(REPORTED_DEICTIC, 1,
       OPEN, DEMONSTRATIVE, " ", v("fixes|solves|settles|explains|proves|ends", "finite", "transitive"),
       " ", phrase(OBJ, rule="np_indef_pron"), EXCLSTOP, CLOSE, " ",
       scoped("gasped|panted|choked|breathed|sighed|muttered|whispered", "V", vform="finite", subcat="clausal"), " ",
       scoped("one|someone|somebody", "PRONOUN", indefinite_human="true"), STOP, speech=True)

ADJ_RECKON = "dialogue_structural_adjectival_echo_reckoning_and_separate_assertion"
family(ADJ_RECKON, 3,
       OPEN, labelled("echo", lx("Blue|Drunk|Mad|Sick|Lost|Cold|Hungry|Dead", "ADJ")), EXCLSTOP, " ",
       scoped("Well|Yes|Indeed", "STANCE", turn_particle="true"), COMMA, " ", subject("I|we"),
       " ", v("reckon|think|suppose|believe|imagine", "base", "clausal"), " ", subject(), " ", COP_PAST, " ",
       lx(r"(?i:(?P=echo))", "ADJ"), STOP, " ",
       DEMONSTRATIVE, lx("[’']s", "COPULA"), " ", lx("a", "DET"), " ",
       lx("true|fair|wise|good|plain|fine", "ADJ"), " ", lx("word|remark|statement|answer|observation", "N"),
       STOP, CLOSE, speech=True, sequence=True)

AFFIRMATIVE_ELLIPSIS = "dialogue_structural_exclamation_modal_ellipsis_and_epistemic_incise"
family(AFFIRMATIVE_ELLIPSIS, 2,
       OPEN, OH, EXCLSTOP, " ", subject(r"I|We|You|He|She|They"),
       " ", lx("really|certainly|surely|indeed", "ADV"), " ",
       lx("will|would|can|could|should|must", "MODAL"), COMMA, " ", subject("you"),
       " ", v("know|see|understand", "base", "intransitive"), EXCLSTOP, CLOSE,
       " ", subject(), " ", REPORT_INTRO, STOP, speech=True, sequence=True)

INTRODUCED_ADDRESS = "dialogue_structural_disclosed_speech_of_initiated_conversation"
family(INTRODUCED_ADDRESS, 1,
       lx("In", "PREP"), " ", lx("a|an", "DET"), " ",
       lx("doleful|solemn|quiet|cheerful|sober|faint|loud|earnest|anxious", "ADJ"), " ",
       lx("voice|tone", "N"), " ", name(r"(?:Mr\.|Mrs\.|Dr\.) +[A-Z][a-z]+|[A-Z][a-z]+"), " ",
       v("began|opened|started|resumed", "finite", "transitive"),
       " ", lx("the", "DET"), " ", lx("projected|anticipated|planned|long|painful|private|unpleasant", "ADJ"),
       " ", lx("conversation|discussion|interview|exchange|dialogue", "N"), mark(":", "COLON"), " ",
       OPEN, OH, EXCLSTOP, " ", name(r"(?:Mr\.|Mrs\.|Dr\.) +[A-Z][a-z]+|[A-Z][a-z]+"), EXCLSTOP, CLOSE,
       speech=True, sequence=True)

COUNTERFACTUAL_REPORT = "dialogue_structural_reported_affirmation_and_perfect_negative_condition"
family(COUNTERFACTUAL_REPORT, 3,
       OPEN, DEMONSTRATIVE, " ", COP_PRESENT, " ", lx("very|quite|perfectly|certainly|entirely", "DEGREE"),
       " ", lx("true|right|fair|reasonable|just", "ADJ"), *SEP_TAG, REPORT_INTRO,
       " ", name(), *RESTART, AND, " ", subject(), " ", lx("could|would|might", "MODAL"), " ",
       lx("easily|readily|gladly|willingly", "ADV"), " ",
       v("forgive|excuse|overlook|pardon|forget", "base", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:pride|anger|vanity|mistake|imprudence|fault|error|offence)", rule="np_poss"),
       COMMA, " ", lx("if", "CONJ"), " ", subject(), " ", HAD, " ", NOT, " ",
       v("mortified|hurt|wounded|offended|injured|insulted|damaged", "ed", "transitive"),
       " ", scoped("mine|yours|hers|his|ours|theirs", "POSS-PROFORM", independent_possessive="true"),
       STOP, CLOSE, speech=True, sequence=True)

TEMPORAL_CLEFT = "structural_temporal_focus_cleft_with_calendar_end"
family(TEMPORAL_CLEFT, 2,
       scoped("It", "EXPL", cleft_expletive="true"), " ", COP_PAST, " ", lx("in|at", "PREP"), " ",
       lx("the", "DET"), " ", lx("latter|earlier|very", "ADJ"), " ", lx("end|part|beginning", "N"), " ",
       OF, " ", scoped(r"January|February|March|April|May|June|July|August|September|October|November|December", "MONTH"),
       " ", lx("that", "COMP-THAT"), " ", subject(), " ", lx("again|finally|at last", "ADV"), " ",
       v("quitted|quit|left|abandoned|revisited|re-entered", "finite", "transitive"), " ",
       lx(POSSESSIVE, "POSS", anaphor="true"), " ", lx("native|old|new|former|familiar", "ADJ"), " ",
       lx("country|home|village|house|residence|town|city", "N"), STOP)

IMAGE_AND_PURSUIT = "structural_semicolon_mental_image_then_independent_copular_control"
family(IMAGE_AND_PURSUIT, 2,
       lx("But|And", "COORD"), " ", lx("in", "PREP"), " ", name(), " ", subject(),
       " ", v("saw|recognized|discerned|found|noticed", "finite", "transitive"), " ",
       lx("the", "DET"), " ", lx("image|likeness|reflection|portrait", "N"), " ", OF, " ",
       POS, " ", lx("former|old|younger|earlier", "ADJ"), " ", lx("self", "N"), SEMI,
       " ", subject(), " ", COP_PAST, " ", lx("inquisitive|curious|eager|alert|keen|inspired|attentive", "ADJ"),
       " ", AND, " ", lx("anxious|eager|ready|keen|willing", "ADJ"), " ", TO, " ",
       v("gain|acquire|get|gather|obtain", "base", "transitive"),
       " ", phrase("experience|knowledge|skill|confidence|insight", rule="np_bare"), " ", AND, " ",
       phrase("instruction|guidance|advice|wisdom|assistance|information", rule="np_bare"), STOP)

EXISTENTIAL_SEEM = "structural_speaker_stance_incise_before_existential_claim"
family(EXISTENTIAL_SEEM, 2,
       scoped("Well|Indeed|Yes", "STANCE", turn_particle="true"), COMMA, " ",
       lx("as", "CONJ"), " ", scoped("it", "EXPL", stance_expletive="true"), " ",
       v("seemed|appeared", "finite", "linking"), " ", lx("to", "PREP"), " ",
       phrase(OBJ, rule="np_indef_pron"), COMMA, " ", lx("there", "EXPL"), " ", COP_PAST,
       " ", lx("some|little|no", "DET"), " ", lx("sense|wisdom|reason|hope|truth|comfort", "N"), " ",
       lx("in", "PREP"), " ", scoped("this|that", "DEMONSTRATIVE-PRONOUN", deictic="true"), STOP)

BRIEF_ABSENCE = "structural_restrictive_duration_then_temporally_anchored_speech"
family(BRIEF_ABSENCE, 2,
       name(), " ", COP_PAST, " ", lx("gone|away|absent", "ADJ"), " ",
       scoped("but|only", "DEGREE", restrictive="true"), " ", lx("a", "DET"), " ",
       lx("little|short|brief", "ADJ"), " ", lx("while|time|interval|period", "N"), COMMA, " ",
       AND, " ", lx("during", "PREP"), " ", phrase(rf"(?:{POSSESSIVE}) +(?:absence|visit|sleep)", rule="np_poss"),
       " ", name(), " ", v("spoke|talked|whispered|went|read", "finite", "intransitive"),
       " ", lx("straight|quietly|softly", "ADV"), " ", lx("on", "PARTICLE"), " ",
       lx("in|into", "PREP"), " ",
       phrase(r"the +(?:cook|doctor|captain|sailor|servant|guard|teacher)[’']s +ear", rule="np_genitive"),
       STOP)

NECESSITY_ABSOLUTE = "structural_necessity_motion_state_with_coordinated_absolutes"
family(NECESSITY_ABSOLUTE, 1,
       scoped("So|Thus", "ADV", consequence="true"), " ", lx("there|here", "ADV"), " ", subject(), " ", HAD,
       " ", TO, " ", v("stay|remain|wait|stand|sit", "base", "intransitive"), mark("--", "DASH"),
       phrase(rf"(?:{POSSESSIVE}) +(?:mother|father|friend|companion|sister|brother)", rule="np_poss"), " ",
       lx("almost|nearly", "DEGREE"), " ", lx("entirely|completely|wholly", "ADV"),
       " ", v("exposed|sheltered|concealed|hidden|protected", "ed", "transitive"), " ", AND,
       " ", lx("both|all", "DET"), " ", OF, " ", phrase("us|them|you", rule="np_indef_pron"),
       " ", lx("within|beyond", "PREP"), " ", lx("earshot|sight|reach|range", "N"),
       " ", OF, " ", phrase(rf"the +{W}", rule="np_det_n"), STOP)

PERCEPTION_PURPOSE = "structural_perfect_posture_with_purpose_and_bare_perception_complement"
family(PERCEPTION_PURPOSE, 1,
       subject(r"I|We|You|They|He|She"), " ", ASPECT_HAVE, " ",
       v("stood|stepped|moved|sat|waited", "ed", "intransitive"), " ", lx("aside|back|apart|still", "ADV"),
       " ", TO, " ", v("see|hear|watch|feel|notice", "base", "transitive"), " ",
       lx("the", "DET"), " ", lx("phantoms|shadows|echoes|ghosts|images|memories|fragments", "N"), " ", OF,
       " ", phrase(r"(?:those|these|the) +(?:days|years|months|times|moments|hours)", rule="np_det_n"),
       " ", v("go|pass|walk|move|drift|float", "base", "prepositional"), " ",
       lx("by|past|before|around", "PREP"), " ", phrase(OBJ, rule="np_indef_pron"), STOP)

SEND_WORD = "structural_modal_control_with_parenthetical_and_distinct_transfer_roles"
family(SEND_WORD, 2,
       subject(r"He|She|They|We|I|You"), " ", lx("might|could|would|may", "MODAL"),
       " ", v("desire|wish|want|hope|intend", "base", "subject_control"), COMMA,
       " ", subject("I|we"), " ", v("thought|believed|supposed|imagined|guessed", "finite", "clausal"), COMMA,
       " ", lx("after|before|upon", "PREP"),
       " ", v("receiving|reading|hearing|considering|seeing", "ing", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:communication|message|note|letter|request|proposal|invitation)", rule="np_poss"),
       COMMA, " ", TO, " ", v("send|convey|deliver|carry|give", "base", "transitive"), " ",
       lx("some|a|an", "DET"), " ", scoped("parting|final|short|brief|affectionate|urgent", "ADJ"), " ",
       lx("word|message|letter|note|warning|report", "N"), " ", lx("by|through", "PREP"),
       " ", phrase(OBJ, rule="np_indef_pron"), " ", lx("to", "PREP"), " ",
       POS, " ", lx("unhappy|anxious|distant|absent|worried|old|dear", "ADJ"), " ",
       lx("lover|friend|companion|brother|sister|father|mother|cousin", "N"), STOP)

NEGATIVE_RELATIVE = "structural_negative_proform_extraposed_subject_relative"
family(NEGATIVE_RELATIVE, 2,
       lx("Nothing", "PRONOUN"), " ", v("occurred|happened|passed|arose", "finite", "intransitive"),
       " ", lx("between|among", "PREP"), " ", phrase("them|us|you", rule="np_indef_pron"), " ",
       lx("that|which", "WH-PRONOUN"), " ", lx("could|might|would", "MODAL"), " ",
       v("justify|encourage|support|confirm|warrant", "base", "transitive"), " ",
       lx("the", "DET"), " ", lx("hopes|expectations|suspicions|fears|concerns", "N"), " ", OF, " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:sister|brother|friend|father|mother|uncle|aunt)", rule="np_poss"), STOP)

HAD_CANVASSED = "structural_past_perfect_passive_relative_and_finite_passive_resumption"
family(HAD_CANVASSED, 2,
       subject(r"The +(?:subject|matter|question|proposal|topic|plan|issue)"), " ", lx("which|that", "WH-PRONOUN"),
       " ", HAD, " ", lx("been", "AUX-BE", vform="ed"), " ",
       lx("so|very|rather|quite", "DEGREE"), " ", lx("[a-z]+ly", "ADV"), " ",
       v("canvassed|debated|discussed|argued|weighed|considered", "ed", "transitive"), " ",
       lx("between|among", "PREP"),
       " ", phrase(rf"(?:{POSSESSIVE}) +(?:parents|friends|families|elders|counsellors|advisers)", rule="np_poss"),
       COMMA, " ", scoped("about|nearly|almost", "DEGREE", approximative="true"), " ", lx("a|one", "DET"), " ",
       lx("twelvemonth|year|month|week|fortnight|day", "N"), " ", lx("ago", "ADV"),
       COMMA, " ", PAST_BE, " ", lx("now|then", "ADV"), " ",
       v("brought|put|carried", "ed", "transitive"), " ", lx("forward", "ADV"), " ", lx("again", "ADV"),
       STOP)

DUAL_PASSIVE_CONTROL = "structural_shared_passive_control_with_parallel_infinitives"
family(DUAL_PASSIVE_CONTROL, 2,
       lx("Now|Then", "ADV"), " ", subject(), " ", PAST_BE, " ",
       v("led|prompted|induced|moved", "ed", "object_control"), " ", TO,
       " ", v("examine|study|consider|investigate", "base", "transitive"), " ",
       lx("the", "DET"), " ", lx("cause|origin|source|nature", "N"), " ", AND, " ",
       lx("progress|growth|course|development|outcome", "N"), " ", OF,
       " ", phrase(r"(?:this|that|the) +(?:decay|change|growth|disease|disorder|process)", rule="np_det_n"),
       " ", AND, " ", v("forced|obliged|compelled|required", "ed", "object_control"), " ", TO, " ",
       v("spend|pass", "base", "transitive"),
       " ", phrase("days|hours|weeks|months|years", rule="np_bare"), " ", AND, " ",
       phrase("nights|evenings|mornings|days|weekends", rule="np_bare"), " ",
       lx("in", "PREP"), " ", phrase(W, rule="np_bare"), " ", AND, " ", phrase(W, rule="np_bare"), STOP)

NEAR_OVERBOARD = "structural_repeated_posture_with_proximity_to_spatial_state"
family(NEAR_OVERBOARD, 2,
       subject(r"I|We|They|He|She|You"), " ", v("dropped|fell|knelt|settled|sat", "finite", "intransitive"),
       " ", lx("upon|on|onto", "PREP"),
       " ", phrase(r"the +(?:thwart|deck|bench|floor|ground|seat|step)", rule="np_det_n"),
       " ", lx("again", "ADV"), COMMA, " ", scoped("none too soon", "ADV", marginal_time="true"),
       COMMA, " ", lx("for", "COORD"), " ", subject(), " ", COP_PAST,
       " ", scoped("near|nearly|almost", "DEGREE", proximity="true"), " ",
       lx("overboard|ashore|underwater|adrift", "ADV"), STOP)

SOOTHING_CAUSE = "structural_coordinated_adjectival_predication_with_scoped_causal_clause"
family(SOOTHING_CAUSE, 2,
       subject(r"This +(?:imagination|thought|idea|notion|memory|vision|dream|recollection|prospect)"),
       " ", COP_PAST, " ", lx("dreadful|terrible|painful|distressing|alarming|unpleasant", "ADJ"),
       " ", lx("in", "PREP"), " ", lx("itself", "PRONOUN"), COMMA, " ", BUT, " ",
       lx("soothing|reassuring|comforting|encouraging|relieving|pleasant", "ADJ"), " ",
       scoped("inasmuch as|insofar as|in so far as|because", "CONJ", causative="true"), " ", subject("it"),
       " ", v("supposed|implied|indicated|suggested|meant|assumed", "finite", "transitive"),
       " ", lx("the", "DET"), " ", lx("safety|welfare|health|survival|comfort|happiness", "N"),
       " ", OF, " ", phrase(rf"(?:{POSSESSIVE}) +(?:friends|family|parents|children|companions)", rule="np_poss"),
       STOP)

HOW_ACQUAINTED = "structural_acquainted_with_nominal_and_embedded_manner_interrogative"
family(HOW_ACQUAINTED, 2,
       subject(r"You|We|They|He|She|I"), " ", COP_PRESENT, " ", lx("well|perfectly|closely", "ADV"),
       " ", lx("acquainted|familiar", "ADJ"), " ", lx("with", "PREP"),
       " ", phrase(rf"(?:{POSSESSIVE}) +(?:failure|disappointment|loss|trouble|defeat|success|escape)", rule="np_poss"),
       " ", AND, " ", lx("how", "WH-NOM", wh_adverbial="true"), " ", lx("[a-z]+ly", "ADV"), " ", subject(),
       " ", v("bore|took|felt|endured|sustained|accepted|received", "finite", "transitive"),
       " ", phrase(r"the +(?:disappointment|failure|loss|blow|news|injury|shock|criticism)", rule="np_det_n"), STOP)

NEITHER_CAUSE = "structural_temporal_first_clause_and_neither_nor_causal_subject"
family(NEITHER_CAUSE, 3,
       subject(r"She|He|I|We|They|You"), " ", v("coloured|blushed|frowned|smiled|flinched|shuddered", "finite", "intransitive"),
       " ", lx("as|when|while", "CONJ"), " ", subject(),
       " ", v("spoke|talked|laughed|sighed|paused", "finite", "intransitive"), SEMI, " ", BUT, " ",
       scoped("neither", "NEG-COORD", negative_coordination="true"), " ", DEMONSTRATIVE, COMMA, " ",
       lx("nor", "COORD"), " ", scoped("anything else|something else|anyone else", "PRONOUN", alternative="true"),
       COMMA, " ", v("awakened|aroused|raised|provoked|caused|produced", "finite", "transitive"),
       " ", lx("a", "DET"), " ", lx("suspicion|doubt|fear|premonition|sense", "N"),
       " ", OF, " ", phrase(r"the +(?:truth|danger|scheme|matter|deceit|plot|deception)", rule="np_det_n"), STOP)

SIMILE_RELATIVE = "structural_motion_simile_with_reduced_passive_and_zero_relative"
family(SIMILE_RELATIVE, 2,
       subject(r"I|He|She|We|They|You"), " ", v("walked|wandered|roamed|paced|moved", "finite", "prepositional"),
       " ", lx("about|around|through|across", "PREP"), " ",
       phrase(r"the +(?:isle|island|village|room|town|house|garden)", rule="np_det_n"), " ",
       lx("like", "PREP"), " ", lx("a|an", "DET"), " ", lx("restless|weary|sad|lonely|lost", "ADJ"),
       " ", lx("spectre|ghost|spirit|stranger|wanderer|traveller", "N"), COMMA, " ",
       v("separated|parted|banished|cut", "ed", "transitive"), " ", lx("from", "PREP"), " ",
       scoped("all|everything", "PRONOUN", universal="true"), " ", subject("it"),
       " ", v("loved|knew|cherished|remembered|valued", "finite", "transitive"), " ", AND, " ",
       lx("miserable|unhappy|wretched|lonely|sad", "ADJ"), " ", lx("in", "PREP"), " ",
       phrase(r"the +(?:separation|solitude|distance|exile|loneliness)", rule="np_det_n"), STOP)

MAKE_FOR_SHORE = "structural_phrasal_departure_and_goal_with_event_comparative"
family(MAKE_FOR_SHORE, 3,
       name(), " ", AND, " ", subject("I"), " ", v("got|climbed|went|stepped|jumped", "finite", "intransitive"),
       " ", lx("out|down|up", "PARTICLE"), " ", lx("through|across|from", "PREP"), " ",
       phrase(r"the +(?:stern-port|hatch|doorway|door|window|gate|arch|passage)", rule="np_det_n"), COMMA,
       " ", AND, " ", subject("we"), " ",
       scoped("made|headed|set off", "V", vform="finite", subcat="goal_motion"), " ", lx("for", "PREP"),
       " ", phrase(r"shore|land|home|safety|shelter", rule="np_bare"), " ", lx("again", "ADV"),
       " ", lx("as", "CONJ"), " ", lx("fast|quickly|swiftly|rapidly", "ADV"), " ", lx("as", "CONJ"),
       " ", phrase(r"oars|sails|horses|winds|the +current|the +wind"), " ",
       lx("could|might|would", "MODAL"), " ", v("take|carry|drive", "base", "transitive"),
       " ", phrase("us", rule="np_indef_pron"), STOP)

NEVER_SAID = "dialogue_structural_modal_negative_perfect_with_titled_finite_content"
family(NEVER_SAID, 2,
       OPEN, subject(r"I|We|He|She|They|You"), " ", lx("should|would|could|might", "MODAL"), " ",
       lx("never", "DEGREE", negation="true"), " ", lx("have", "HAVE", vform="base"), " ",
       v("said|thought|supposed|believed|imagined", "ed", "clausal"), " ",
       name(r"(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+"), " ", COP_PAST, " ",
       lx("settled|established|comfortable|contented", "ADJ"), " ", lx("near|beside|among", "PREP"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:family|parents|friends|relatives|brothers|sisters)", rule="np_poss"),
       STOP, CLOSE, speech=True, sequence=True)

OPPOSITE_INN = "structural_motion_with_adverbial_participle_and_pied_piped_locative_relative"
family(OPPOSITE_INN, 2,
       v("Continuing|Proceeding|Walking|Traveling|Travelling|Riding", "ing", "intransitive"), " ",
       scoped("thus|onward|onwards|on", "ADV", continuative_manner="true"), COMMA, " ", subject(),
       " ", v("came|arrived|drew|pulled", "finite", "intransitive"), " ",
       scoped("at length|at last|eventually|finally", "ADV", culmination="true"), " ",
       scoped("opposite to|opposite|abreast of", "PREP", orientation="true"), " ",
       phrase(r"the +(?:inn|hotel|house|bridge|station|tavern|shop|post)", rule="np_det_n"), " ",
       lx("at|by|near", "PREP"), " ", lx("which", "WH-PRONOUN"), " ",
       lx("the", "DET"), " ", lx("various|different|several|many", "ADJ"), " ",
       lx("diligences|coaches|wagons|carts|carriages|buses|trains", "N", number="plural"), " ", AND, " ",
       phrase(r"carriages|carts|coaches|wagons|trains|buses", rule="np_bare"), " ",
       lx("usually|often|regularly|frequently|sometimes", "ADV"), " ",
       v("stopped|halted|paused|arrived|waited", "finite", "intransitive"), STOP)

COPULAR_TAG_GESTURE = "dialogue_structural_copular_echo_tag_with_controlled_report_depictive"
family(COPULAR_TAG_GESTURE, 2,
       OPEN, DEMONSTRATIVE, lx("[’']s", "COPULA"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:sort|choice|answer|style|idea|decision|plan)", rule="np_poss"), COMMA, " ",
       lx("is", "COPULA", vform="finite"), " ", subject("it"), QMARK, CLOSE, " ", subject(),
       " ", REPORT_INTRO, COMMA, " ",
       v("returning|raising|lifting|holding|bringing|taking", "ing", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:pipe|cup|glass|hand|finger|handkerchief|hat)", rule="np_poss"), " ",
       lx("to|towards|toward", "PREP"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:mouth|lips|face|ear|head|nose|chin)", rule="np_poss"),
       STOP, speech=True)

LOCATIVE_ADDRESS = "dialogue_structural_named_location_with_appositive_and_true_vocative"
family(LOCATIVE_ADDRESS, 1,
       OPEN, subject(r"You|We|They|He|She|I"), " ", COP_PRESENT, " ", lx("at|in", "PREP"), " ",
       lx("the", "DET"), " ", scoped("Admiral|Captain|General|King|Queen|Prince|Princess", "TITLE", honorific="true"),
       " ", name(r"[A-Z][a-z]+"), COMMA, " ",
       lx(r"[A-Z][a-z]+", "ADJ"), " ", lx(r"[A-Z][a-z]+", "N"), " ",
       lx("Cove|Bay|Harbour|Harbor|Point|Village|Town|Quay", "N"), COMMA, " ",
       POS, " ", lx("good|dear|young|old", "ADJ"), " ", lx("man|woman|friend|fellow|boy|girl", "N"),
       *SEP_TAG, REPORT_INTRO, " ", subject(), STOP, speech=True)

SUMMONED_COORD = "structural_shared_subject_with_prepositional_passive_and_welcome"
family(SUMMONED_COORD, 2,
       phrase(r"(?:My|His|Her|Our|Their|Your) +(?:aunt|sister|friend|mother|father|brother|daughter|son)", rule="np_poss"),
       " ", v("presented|showed", "finite", "transitive"), " ", lx("herself|himself|themselves|myself|ourselves", "PRONOUN"),
       " ", lx("on|upon|after", "PREP"), " ", lx("being", "AUX-BE", vform="ing"), " ",
       scoped("sent", "V", vform="ed", subcat="prepositional_passive"), " ", lx("for", "PREP"),
       COMMA, " ", AND, " ", v("welcomed|greeted|received|addressed", "finite", "transitive"), " ",
       name(r"(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+|[A-Z][a-z]+"), " ",
       lx("with", "PREP"), " ", lx("gracious|warm|genuine|friendly|great", "ADJ"),
       " ", lx("cordiality|warmth|affection|kindness|enthusiasm|sympathy", "N"), STOP)

CURIOSITY_RELATIVE = "dialogue_structural_reported_do_question_with_possessed_curiosity_relative"
family(CURIOSITY_RELATIVE, 2,
       OPEN, lx("And|But", "COORD"), " ", lx("do|did", "AUX"), " ", subject(),
       " ", lx("really|certainly|actually|truly", "ADV"), " ",
       v("know|remember|understand|believe|recognize", "base", "transitive"),
       " ", lx("all", "DET"), " ", DEMONSTRATIVE, QMARK, CLOSE, " ", REPORT_INTRO, " ",
       name(r"(?:Mr\.|Mrs\.|Dr\.|Miss) +[A-Z][a-z]+|[A-Z][a-z]+"), COMMA, " ", lx("whose", "WH-PRONOUN"),
       " ", lx("curiosity|concern|interest|anxiety|doubt", "N"), " ",
       scoped("as to|with regard to|concerning|about", "PREP", aboutness="true"), " ",
       lx("the", "DET"), " ", lx("mode|source|origin|means|nature", "N"), " ", OF, " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:intelligence|information|news|knowledge|report|account)", rule="np_poss"),
       " ", COP_PAST, " ", scoped("all|entirely|wholly", "DEGREE", total_degree="true"),
       " ", lx("alive|awake|active|present|evident", "ADJ"), STOP, speech=True)

NEGATED_INFERENCE = "dialogue_structural_reply_reprise_and_expletive_negative_inference"
family(NEGATED_INFERENCE, 3,
       OPEN, subject(r"You|We|They|He|She"), " ", lx("certainly|surely|really|indeed", "ADV"),
       " ", lx("do|does|did", "AUX"), *SEP_TAG, subject(), " ", REPORT_INTRO, " ", lx("with", "PREP"), " ",
       phrase(r"a +(?:smile|frown|shrug|laugh|sigh)", rule="np_det_n"), SEMI, " ", OPEN, BUT, " ",
       scoped("it", "EXPL", inference_expletive="true"), " ", lx("does|did", "AUX"), " ", NOT,
       " ", scoped("follow", "V", vform="base", subcat="extraposed_clausal"), " ",
       lx("that", "COMP-THAT"), " ", phrase(r"the +(?:interruption|request|announcement|remark|visit|proposal)", rule="np_det_n"),
       " ", lx("must|should|could|can", "MODAL"), " ", BE_BASE, " ",
       lx("unwelcome|welcome|necessary|unnecessary|wrong|right", "ADJ"), STOP, CLOSE,
       speech=True, sequence=True)

FOUND_PROGRESSIVE = "structural_progressive_travel_with_discovery_of_shared_subject_coordination"
family(FOUND_PROGRESSIVE, 4,
       subject(r"We|They|You|He|She|I"), " ", PAST_BE, " ",
       v("crossing|walking|going|travelling|proceeding|riding", "ing", "prepositional"),
       " ", lx("to|towards|toward", "PREP"), " ", lx("the", "DET"), " ",
       lx("former|latter|next|other|usual", "ADJ"), " ", lx("place|town|village|station|house|bridge", "N"),
       COMMA, " ", lx("when", "CONJ"), " ", subject(),
       " ", v("found|discovered|noticed|learned|observed", "finite", "clausal"), " ", lx("that", "COMP-THAT"),
       " ", phrase(rf"(?:{POSSESSIVE}) +(?:aunt|sister|mother|friend|brother|father|companion)", rule="np_poss"),
       " ", lx("greatly|markedly|slightly|rapidly|gradually|quickly", "ADV"), " ",
       v("accelerated|increased|reduced|slowed|changed", "finite", "transitive"), " ",
       phrase(rf"(?:{POSSESSIVE}) +(?:speed|pace|gait|stride)", rule="np_poss"), COMMA, " ", AND,
       " ", v("looked|seemed|appeared", "finite", "linking"), " ",
       lx("frightened|worried|alarmed|relieved|tired|happy|nervous|uneasy", "ADJ"), STOP)
