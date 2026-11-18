"""Original-span gates for nested, interrupted, and coordinated constructions."""
from __future__ import annotations

from .scoped_attachment_domains import (
    ASPECT_HAVE, AND, BE_BASE, BUT, CLOSE, COMMA, COP_PAST, COP_PRESENT, DEMONSTRATIVE,
    EXCLSTOP, HAD, NOT, OBJ, OF, OH, OPEN, PAST_BE, POS, POSSESSIVE, PRON, QMARK,
    REPORT_INTRO, SEMI, STOP, TO, W, family, lx, mark, name, phrase, scoped, subject, v,
)

NARRATIVE, SPOKEN, SEQUENCES, COUNTS = [], [], [], {}
REGISTRY = NARRATIVE, SPOKEN, SEQUENCES, COUNTS
DASH = mark("--", "DASH")
TITLE_NAME = r"(?:Mr\.|Mrs\.|Dr\.|Miss|Captain|Master) +[A-Z][a-z]+"
FULL_PRON = r"I|[Ww]e|[Tt]hey|[Yy]ou|[Hh]e|[Ss]he|[Ii]t"
NUMERAL = r"one|two|three|four|five|six|seven|eight|nine|ten"
CONTENT_THAT = lx("that", "COMP-THAT")
RELATIVE = lx("which|that", "WH-PRONOUN")
BASE_HAVE = lx("have", "HAVE", vform="base")
PERTINENT_COP = lx("been", "COPULA", vform="ed")


def define(root, count, *spans, speech=False):
    """Keep punctuation adjacent while retaining every original delimiter."""
    layout = []
    for span in spans:
        if layout and span.category not in {"COMMA", "DASH", "SPEECH-STOP", "SEMICOLON", "QMARK", "CLOSE-QUOTE", "ABBREVIATION-STOP"} \
                and layout[-1].category not in {"OPEN-QUOTE", "DASH"} \
                and span.features.get("genitive_clitic") != "true" \
                and span.pattern not in {r"[’']s", r"[’']ll"}:
            layout.append(" ")
        layout.append(span)
    family(root, count, *layout, speech=speech, sequence=speech, registry=REGISTRY)


def pp(pattern):
    return lx(pattern, "PREP")


def adv(pattern):
    return lx(pattern, "ADV")


def adj(pattern):
    return lx(pattern, "ADJ")


def det(pattern):
    return lx(pattern, "DET")


def noun(pattern):
    return lx(pattern, "N")


def nom(pattern, rule=None):
    return phrase(pattern, rule=rule)


def possess(pattern):
    return nom(rf"(?:{POSSESSIVE}) +(?:{pattern})", "np_poss")


def obj(pattern=OBJ):
    return nom(pattern, "np_indef_pron")


def s(pattern=FULL_PRON):
    return subject(pattern)


def finite(pattern, frame):
    return v(pattern, "finite", frame)


def base(pattern, frame):
    return v(pattern, "base", frame)


def participle(pattern, frame):
    return v(pattern, "ed", frame)


def ing(pattern, frame):
    return v(pattern, "ing", frame)


def conjunction(pattern):
    return lx(pattern, "CONJ")


def modal(pattern):
    return lx(pattern, "MODAL")


def degree(pattern):
    return lx(pattern, "DEGREE")


ANCHORED_DURATION = "structural_elapsed_reduced_passive_with_two_distinct_relatives"
define(ANCHORED_DURATION, 3, pp("After"), det("some|several|a few"),
    noun("days|weeks|months|hours"), participle("spent|passed", "transitive"), pp("in"),
    adj("listless|quiet|miserable|utter|silent"), noun("indolence|silence|solitude|idleness|retirement"),
    COMMA, pp("during|throughout"), RELATIVE, s(), finite("traversed|crossed|covered|travelled", "transitive"),
    det("many|several"), noun("leagues|miles|kilometres"), COMMA, s(), finite("arrived|stopped|paused", "prepositional"),
    pp("at|in"), name(), COMMA, lx("where", "WH-NOM"), s(), finite("waited|stayed|remained", "intransitive"),
    lx(NUMERAL, "NUM"), noun("days|weeks|hours"), pp("for"), name(), STOP)

WH_COORD_REASON = "structural_modal_wh_object_and_simultaneous_alternative_actions"
define(WH_COORD_REASON, 3, lx("Who", "WH-PRONOUN"), modal("shall|could|can|would"),
    base("conceive|imagine|understand|describe", "transitive"), det("the"), noun("horrors|labours|burdens|details|dangers"),
    OF, POS, adj("secret|private|lonely|hidden"), noun("toil|work|task|undertaking"),
    conjunction("as|while"), s(), finite("dabbled|worked|searched|laboured", "prepositional"),
    pp("among|in"), det("the"), adj("unhallowed|dark|silent|deserted"), noun("damps|depths|shadows|recesses"), OF,
    nom(r"the +(?:grave|cellar|vault|cave|forest)", "np_det_n"),
    lx("or", "COORD"), finite("tortured|examined|probed|dissected", "transitive"), det("the"),
    adj("living|helpless|wounded|wild"), noun("animal|creature|insect|bird|specimen"),
    TO, base("animate|restore|revive|awaken|preserve", "transitive"),
    det("the"), adj("lifeless|inert|still|silent|fragile"), noun("clay|body|specimen|creature|figure"), QMARK)

ALONE_CIRCUMSTANCE = "structural_shared_posture_breathing_and_depictive_with_genitive"
define(ALONE_CIRCUMSTANCE, 3, s(), scoped("slipped|drew|lifted|pushed|turned", "V", vform="finite", subcat="transitive"),
    nom(r"the +(?:bolt|latch|handle|lever|catch)", "np_det_n"),
    scoped("at once|immediately", "ADV", immediate="true"), COMMA, AND, s(), finite("stood|sat|stayed|waited", "intransitive"),
    AND, finite("panted|rested|shivered|breathed|waited", "intransitive"),
    pp("for"), nom(r"a +(?:moment|while|minute|second)", "np_det_n"),
    pp("in"), nom(r"the +(?:dark|cold|silence|shadow)", "np_det_n"), COMMA, adj("alone"),
    pp("in"), nom(r"the +(?:house|cabin|room|hall|shed)", "np_det_n"),
    pp("with"), det("the"), adj("dead|fallen|injured|sick"), noun("captain|sailor|guard|man|soldier"),
    lx("[’']s", "POSS", genitive_clitic="true"), noun("body|corpse|form"), STOP)

INTERVAL_SPEECH = "structural_temporally_framed_belief_with_controlled_speaking_and_interval_relative"
define(INTERVAL_SPEECH, 4, adv("Sometimes|Often|Occasionally"), COMMA, pp("after|before"), DEMONSTRATIVE,
    COMMA, s(), finite("fancied|believed|thought|imagined|supposed", "clausal"), CONTENT_THAT,
    s(), finite("tried|attempted|began|wanted", "subject_control"), TO, base("speak|talk|reply", "intransitive"),
    degree("even|only"), pp("to"), obj(), COMMA, pp("in|at"), noun("intervals|moments|times"),
    conjunction("when"), s(), PAST_BE, participle("left|kept", "transitive"), adj("alone|quiet|apart"), STOP)

BASKET_RELATIVE = "structural_possession_located_on_body_with_modal_relative_and_counterfactual"
define(BASKET_RELATIVE, 3, name(), finite("had|held|carried|kept", "transitive"), det("a"),
    noun("basket|bag|packet|parcel|box"), OF, nom(r"refreshments|provisions|food|supplies|cakes", "np_bare"),
    pp("on|upon"), possess("knee|lap|arm|shoulder"), COMMA, RELATIVE,
    modal("would|could|might"), BASE_HAVE, participle("lasted|served|sustained", "transitive"), obj("us|them|you"),
    lx("out", "PARTICLE"), adv("handsomely|easily|comfortably|amply"), COMMA, conjunction("if"),
    s(), HAD, lx("been", "AUX-BE", vform="ed"), ing("going|travelling|walking|riding", "prepositional"),
    pp("to"), name(), pp("by"), nom(r"the +same +(?:conveyance|coach|route|train|carriage|boat)", "np_det_n"), STOP)

COFFIN_RELATIVE = "structural_semicolon_shared_motion_two_locative_relatives_and_passive_reading"
define(COFFIN_RELATIVE, 4, s(), finite("alighted|stopped|paused|disembarked", "intransitive"),
    SEMI, AND, finite("followed|accompanied|escorted", "transitive"), det("the"), adj("plain|small|dark|wooden|white"),
    noun("coffin|bier|casket|carriage|procession"), pp("to"), det("a"), noun("corner|place|spot|grave"),
    s(), finite("remember|recall|know|recognise", "transitive"), adv("well|clearly|distinctly"), COMMA,
    lx("where", "WH-NOM"), nom(r"the +(?:service|prayer|ceremony|passage|lesson)", "np_det_n"),
    PAST_BE, scoped("read|recited|spoken", "V", vform="ed", subcat="transitive"),
    ing("consigning|committing|commending|returning", "transitive"), obj(),
    pp("to"), nom(r"the +(?:dust|earth|ground|grave)", "np_det_n"), STOP)

CUSTOMARY_MOTION = "structural_initial_time_with_custom_comparative_and_separate_mover"
define(CUSTOMARY_MOTION, 3, pp("After|Before"), nom(r"tea|dinner|lunch|breakfast|supper", "np_bare"),
    COMMA, name(TITLE_NAME), finite("retired|went|withdrew|walked", "prepositional"),
    pp("to"), nom(r"the +(?:library|study|parlour|room|garden)", "np_det_n"), COMMA,
    conjunction("as"), COP_PAST, possess("custom|habit|practice|wont"), COMMA, AND,
    name(), finite("went|walked|hurried|ran", "intransitive"),
    scoped("up stairs|upstairs|down stairs|downstairs", "ADV", directed_stairs="true"),
    pp("to"), possess("instrument|room|piano|desk|work|book"), STOP)

HIRED_AND_UNFAMILIAR = "structural_historical_post_horses_and_neither_nor_recognition"
define(HIRED_AND_UNFAMILIAR, 3, nom(r"The +(?:horses|ponies)", "np_det_n"), COP_PAST,
    scoped("post|hired", "ADJ", hired_post="true"), SEMI, AND, scoped("neither", "NEG-COORD"),
    nom(r"the +(?:carriage|coach|chariot)", "np_det_n"), COMMA, lx("nor", "COORD"),
    det("the"), noun("livery|clothes|uniform|coat"), OF, nom(r"the +(?:servant|driver|attendant|footman)", "np_det_n"),
    lx("who", "WH-PRONOUN"), finite("preceded|followed|escorted|guided", "transitive"), obj("it"),
    COMMA, COP_PAST, adj("familiar|known|recognisable|recognizable"), pp("to"), obj("them|us|him|her"), STOP)

ADDITIVE_VANTAGE = "structural_causal_advantage_with_visual_coordination_in_embedded_content"
define(ADDITIVE_VANTAGE, 4, nom(r"The +(?:ladies|gentlemen|children|visitors|guests)", "np_det_n"), COP_PAST,
    scoped("somewhat|rather|much", "DEGREE", mitigator="true"), degree("more|less"), adj("fortunate|lucky|comfortable|successful"),
    COMMA, lx("for", "COORD"), s(), finite("had|enjoyed|possessed", "transitive"), det("the"),
    noun("advantage|benefit|pleasure|chance|opportunity"), OF,
    ing("ascertaining|discovering|observing|seeing|learning", "clausal"), pp("from"),
    nom(r"an? +(?:upper|open|high|nearby) +(?:window|balcony|terrace)", "np_det_n"), CONTENT_THAT,
    s(), finite("wore|carried|held", "transitive"), det("a"), adj("blue|black|brown|red|white|grey|green"),
    noun("coat|jacket|cloak|hat|vest"), COMMA, AND, finite("rode|mounted|led", "transitive"),
    det("a"), adj("black|brown|white|grey|bay|chestnut"), noun("horse|pony|mare|steed"), STOP)

DURATION_OF_AGE = "structural_negated_age_perfect_and_when_passive_control"
define(DURATION_OF_AGE, 2, name(TITLE_NAME), HAD, NOT, PERTINENT_COP,
    scoped("of age|in office|in power", "ADJ", measured_status="true"), lx(NUMERAL, "NUM"),
    noun("years|months|weeks|days"), COMMA, conjunction("when"), s(), PAST_BE,
    participle("tempted|persuaded|induced|prompted|encouraged", "object_control"),
    pp("by"), det("a|an"), adj("accidental|unexpected|casual|generous|timely"),
    noun("recommendation|suggestion|invitation|offer|request"), TO, base("look|glance|stare", "prepositional"), pp("at"),
    name(), STOP)

EMOTION_BALANCE = "structural_balanced_affective_nominals_with_relative_and_possessive_gerund"
define(EMOTION_BALANCE, 2, det("The"), scoped("former|latter", "PRONOUN"),
    PAST_BE, participle("divided|torn|split", "transitive"), pp("between"), noun("admiration|wonder|approval|delight"),
    OF, det("the"), noun("brilliancy|brightness|colour|color|glow|warmth"), RELATIVE, noun("exercise|rest|activity|sunlight"),
    HAD, participle("given|lent|brought|added", "transitive"), pp("to"), possess("complexion|skin|face|cheeks"),
    COMMA, AND, noun("doubt|anxiety|concern|uncertainty"),
    scoped("as to|about", "PREP"), det("the"), noun("occasion|situation|event|reason"),
    lx("[’']s", "POSS", genitive_clitic="true"), ing("justifying|warranting|explaining", "transitive"),
    POS, ing("coming|travelling|walking|going|riding", "intransitive"), degree("so|very"), adv("far"),
    adj("alone"), STOP)

PROMISE_CONDITIONAL = "structural_perfect_promise_with_modal_coordination_and_shared_condition"
define(PROMISE_CONDITIONAL, 4, s(), ASPECT_HAVE, participle("promised|sworn|agreed", "clausal"),
    CONTENT_THAT, scoped("someone|somebody|one", "PRONOUN", indefinite_human="true"), modal("should|would"),
    base("watch|look|wait", "prepositional"), pp("for"), obj(), AND, base("give|send", "ditransitive"), obj(),
    adj("instant|immediate|prompt"), noun("notice|warning|news|word"), conjunction("if"),
    det("any|a"), adj("new|strange|unfamiliar"), noun("object|figure|person|vessel|sign"),
    modal("should|might|would"), base("appear|come", "prepositional"), pp("in|within"),
    noun("sight|view|range"), STOP)

LIGHT_PERCEPTION = "structural_anterior_passive_and_affect_with_bare_visual_complement"
define(LIGHT_PERCEPTION, 2, det("The"), noun("windows|doors|lights|lamps"), OF,
    nom(r"the +(?:room|house|hall|chamber|cabin)", "np_det_n"), HAD, adv("before|already|previously"),
    lx("been", "AUX-BE", vform="ed"), participle("darkened|closed|covered|shuttered", "transitive"), COMMA, AND,
    s(), finite("felt|experienced|sensed", "transitive"), det("a"), noun("kind|sort"), OF,
    scoped("panic|dread|terror|fear", "N", affect_nominal="true"), pp("on|upon"), ing("seeing|noticing|watching", "transitive"),
    det("the"), adj("pale|bright|vivid|faint"), adj("yellow|white|blue|green|red"), noun("light|glow"),
    OF, nom(r"the +(?:moon|sun|lamp|candle)", "np_det_n"), base("illuminate|light|brighten", "transitive"),
    nom(r"the +(?:chamber|room|hall|cabin|cellar)", "np_det_n"), STOP)

INVERTED_MOUNTAIN = "structural_locative_relative_orientation_and_inverted_landscape"
define(INVERTED_MOUNTAIN, 3, pp("From"), det("the"), noun("side|bank|shore|hill|ridge|bridge"),
    lx("where", "WH-NOM"), s(), adv("now|then"), finite("stood|sat|waited", "intransitive"),
    name(), COP_PAST, adv("exactly|directly|almost"), scoped("opposite|abreast", "ADV", orientation="true"),
    COMMA, pp("at"), det("the"), noun("distance"), OF, det("a"), noun("league|mile|kilometre"),
    SEMI, AND, pp("above|below|beyond"), obj("it|us|them"), finite("rose|stood|loomed", "intransitive"),
    name(), COMMA, pp("in"), adj("awful|solemn|grim|silent|great"), noun("majesty|splendour|splendor|silence"), STOP)

SEARCH_SEQUENCE = "structural_pointing_relative_then_search_and_independent_passive"
define(SEARCH_SEQUENCE, 4, s(), finite("pointed|gestured|directed", "prepositional"),
    pp("to|towards"), det("the"), noun("spot|place|point|bend|bank"), lx("where", "WH-NOM"),
    s(), HAD, participle("disappeared|vanished|fallen|stopped", "intransitive"), COMMA, AND,
    s(), finite("followed|searched|traced", "transitive"), nom(r"the +(?:track|trail|shore|course)", "np_det_n"),
    pp("with"), noun("boats|torches|dogs|lanterns"), SEMI, noun("nets|ropes|lines"), PAST_BE,
    scoped("cast|thrown|laid|lowered", "V", subcat="transitive", vform="ed"),
    COMMA, BUT, scoped("in vain|without success", "ADV", futility="true"), STOP)

HONORIFIC_PORTRAIT = "structural_foreign_honorific_and_resumed_negative_character_judgment"
define(HONORIFIC_PORTRAIT, 2, scoped("M|Mme", "TITLE", honorific="true"), mark(".", "ABBREVIATION-STOP"),
    name(), COP_PAST, det("a"), adj("little|short|small|tall"), adj("squat|stout|thin|broad|solid"), noun("man|woman|teacher"),
    pp("with"), det("a"), adj("gruff|harsh|cold|shrill|gentle"), noun("voice|manner|bearing"), AND, det("a|an"),
    adj("repulsive|unpleasant|severe|unfriendly|awkward"), noun("countenance|face|expression"),
    SEMI, nom(r"the +(?:teacher|professor|lecturer|master|woman|man)", "np_det_n"),
    COMMA, scoped("therefore|thus|accordingly", "ADV", consequential="true"),
    COMMA, lx("did", "AUX"), NOT, base("prepossess|prejudice|influence|incline|dispose", "transitive"), obj(),
    scoped("in favour of|in favor of|against", "PREP", evaluative="true"), possess("pursuits|studies|interests|plans|work"), STOP)

SHARED_PHRASAL_PERFECT = "structural_two_past_perfects_with_shared_auxiliary_for_marine_actions"
define(SHARED_PHRASAL_PERFECT, 3, lx("And|But", "COORD"), det("the"), adj("next|following"),
    noun("moment|minute|instant"), s(), AND, nom(r"the +(?:captain|sailor|mate|boy|doctor)", "np_det_n"),
    HAD, participle("dropped|jumped|stepped|climbed", "intransitive"), scoped("aboard of|aboard|alongside", "PREP"),
    obj("us|them|him"), COMMA, AND, s(), HAD, participle("shoved|pushed|cast", "transitive"),
    lx("off", "PARTICLE"), AND, scoped("given way|made way|pulled away", "V", vform="ed"), STOP)

EXISTENTIAL_SOUND = "structural_negative_existential_with_two_exceptions_and_sound_source"
define(EXISTENTIAL_SOUND, 1, lx("There", "EXPL"), COP_PAST, det("no"), noun("sound|noise|voice"),
    scoped("but|except", "PREP", exceptive="true"), DEMONSTRATIVE, OF, det("the"),
    adj("distant|near|loud|faint|steady"), noun("breakers|waves|rapids|surf"), COMMA,
    ing("mounting|rising|rolling|breaking", "intransitive"),
    scoped("from all round|from all around|from below|from afar", "ADV", source_direction="true"),
    COMMA, AND, det("the"), noun("chirp|hum|buzz|song|call"), OF, adj("countless|numerous|tiny|small"),
    noun("insects|birds|crickets|flies|beetles"), pp("in"), nom(r"the +(?:brush|grass|trees|wood|reeds)", "np_det_n"), STOP)

BOAT_PURPOSE = "structural_shared_retreat_and_boat_relative_with_genitive_and_purpose"
define(BOAT_PURPOSE, 3, name(), finite("retreated|withdrew|stepped|moved", "prepositional"),
    pp("from"), possess("place|seat|post|position"), pp("in|on"), nom(r"the +(?:gallery|cabin|hall|room|deck)", "np_det_n"),
    AND, finite("dropped|jumped|stepped|climbed", "intransitive"), pp("into|onto"),
    det("the"), noun("boat|launch|skiff|canoe|dinghy"), COMMA, RELATIVE, s(),
    adv("then|now|soon"), finite("brought|took|pulled|towed", "transitive"), adv("round|around|over|back"),
    pp("to"), det("the"), noun("ship|vessel|schooner|boat"), lx("[’']s", "POSS", genitive_clitic="true"),
    noun("counter|stern|bow|side"), COMMA, TO, BE_BASE, scoped("handier|closer|safer|easier|nearer|more convenient", "ADJ", comparative="true"),
    pp("for"), nom(TITLE_NAME), STOP)

HOPELESS_REQUEST = "structural_passive_disorientation_and_asking_with_appositive_resumption"
define(HOPELESS_REQUEST, 3, s(), PAST_BE, participle("bewildered|confused|startled|amazed|surprised", "transitive"),
    SEMI, scoped("it", "EXPL"), finite("seemed|appeared", "linking"), det("a|an"),
    noun("thing|request|demand|proposal|favour|favor"), degree("so|too|quite|very"), adj("hopeless|unlikely|strange|difficult|absurd"),
    s(), PAST_BE, ing("asking|requesting|demanding|proposing", "transitive"), DASH, s(), COMMA, det("the"),
    adj("old|young|tired|stern"), noun("buccaneer|pirate|sailor|captain|leader"), COMMA, det("the"),
    noun("ringleader|leader|instigator|organizer|organiser"), adv("throughout|before|already"), STOP)

NEGATIVE_REPLY_REPORT = "dialogue_structural_negative_self_reply_then_perfect_time_and_plural_agreement"
define(NEGATIVE_REPLY_REPORT, 3, OPEN, scoped("No", "RESPONSE", polarity="negative"), COMMA,
    scoped("sir|madam|captain", "VOCATIVE"), COMMA, NOT, s("I|we"), CLOSE,
    SEMI, AND, scoped("as soon as|immediately after", "CONJ"), s(), HAD,
    participle("said|spoken|uttered|repeated", "transitive"), nom(r"the +(?:words|phrase|command|reply)", "np_det_n"),
    COMMA, s(), finite("think|believe|suppose", "clausal"), s("we|they"), lx("all|both", "PRONOUN"),
    finite("agreed|sided|concurred", "prepositional"), pp("with"), obj(), STOP, speech=True)

GIVING_THEN_REQUEST = "dialogue_structural_temporal_inspection_giving_and_manner_report"
define(GIVING_THEN_REQUEST, 3, pp("After|Upon"), ing("looking|glancing|gazing|staring", "prepositional"),
    pp("at"), obj(), pp("for"), det("some|several|a few"), noun("moments|minutes|seconds"), COMMA,
    s(), finite("gave|handed|passed|returned", "transitive"), obj(), pp("to"), obj(), COMMA, AND,
    REPORT_INTRO, pp("in"), det("a"), adj("low|quiet|faint|gentle|soft"), noun("voice|tone"), COMMA,
    OPEN, lx("Be", "COPULA", vform="base"), scoped("so", "DEGREE", degree_marker="true"), adj("good|kind|obliging"),
    conjunction("as"), base("read|take|examine|open|hold|keep", "transitive"), obj(), COMMA,
    scoped("sir|madam|captain", "VOCATIVE"), STOP, CLOSE, speech=True)

NEGATIVE_PERFECT_WHY = "structural_negative_perfect_why_with_temporal_incise_and_modal_content"
define(NEGATIVE_PERFECT_WHY, 5, lx("Why", "WH-NOM"), scoped("hadn[’']t", "HAVE-NEG"), s(),
    participle("said|mentioned|explained|announced|admitted", "clausal"), COMMA,
    degree("even"), det("the"), noun("day|night|morning|evening|week"),
    conjunction("before"), s(), finite("went|walked|rode|came", "prepositional"), pp("to"),
    nom("church|school|town|bed|work", "np_bare"), COMMA, CONTENT_THAT, s(),
    finite("knew|thought|believed|realized", "clausal"), s(), modal("should|would|might"), BE_BASE,
    adj("uneasy|unhappy|nervous|anxious|afraid|tired"), COMMA, AND, s(), modal("would|could|should"),
    adv("rather"), NOT, QMARK)

NEGATIVE_EDUCATION = "dialogue_structural_existential_tendency_with_epistemic_incise_and_negative_relative"
define(NEGATIVE_EDUCATION, 2, OPEN, lx("There", "EXPL"), COP_PRESENT, COMMA, s(),
    finite("believe|think|suppose|imagine", "clausal"), COMMA, pp("in"),
    nom(r"every +(?:disposition|character|mind|person|temperament)", "np_det_n"), det("a"),
    noun("tendency|inclination|disposition|bias"), pp("to|towards"), det("some"),
    adj("particular|specific|distinct|ordinary"), noun("evil|fault|vice|weakness|error"), DASH, det("a"),
    adj("natural|innate|habitual|deep"), noun("defect|flaw|weakness|fault"), COMMA, RELATIVE, NOT,
    degree("even"), det("the"), adj("best|finest|strongest|greatest"), noun("education|training|discipline|effort"),
    modal("can|could|may|might"), base("overcome|remove|erase|eliminate|alter", "transitive"), STOP, CLOSE, speech=True)

DELIGHT_AND_HOW = "dialogue_structural_extraposed_delight_and_imperative_with_embedded_manner"
define(DELIGHT_AND_HOW, 3, OPEN, scoped("It", "EXPL"), finite("gives|brings|affords", "ditransitive"),
    obj(), det("the"), adj("greatest|utmost|deepest|keenest"), noun("delight|pleasure|joy|satisfaction"),
    TO, base("see|meet|hear|welcome", "transitive"), obj(), SEMI, BUT, base("tell|show|explain", "ditransitive"),
    obj(), lx("how", "WH-NOM", wh_adverbial="true"), s(), finite("left|found|saw|met|greeted", "transitive"),
    possess("father|mother|friend|uncle|aunt"), COMMA, noun("brothers|sisters|children|friends|cousins"),
    COMMA, AND, name(), STOP, CLOSE, speech=True)

INTERJECTION_DIRECTIVE = "dialogue_structural_interjection_report_then_identity_and_conditional_threat"
define(INTERJECTION_DIRECTIVE, 3, OPEN, OH, COMMA, CLOSE, s(),
    scoped("sneered|snapped|growled|grunted", "V", vform="finite", subcat="clausal"), COMMA, OPEN,
    DEMONSTRATIVE, scoped("[’']s", "COPULA", vform="finite"), obj("it|that"), EXCLSTOP,
    base("Take|Lead|Bring|Let|Show", "transitive"), obj(), adv("in|out|inside|outside"),
    adv("straight|quickly|directly|immediately"), lx("or", "COORD"),
    s("I|we|you|he|she|they"), scoped("[’']ll", "MODAL", vform="finite"), base("break|hurt|strike|grab|seize", "transitive"),
    possess("arm|hand|wrist|leg"), STOP, CLOSE, speech=True)

AUXILIARY_REPRISE = "dialogue_structural_acknowledgment_then_debt_with_auxiliary_reprise_and_motion"
define(AUXILIARY_REPRISE, 4, OPEN, scoped("Aye|Yes", "RESPONSE", polarity="positive"), COMMA,
    scoped("aye|yes", "RESPONSE", polarity="positive"), COMMA, CLOSE,
    scoped("returned|replied|answered", "V", vform="finite", subcat="clausal"), name(), SEMI, OPEN, s(),
    scoped("mind|remember|recall", "V", vform="finite", subcat="transitive"), obj(), SEMI,
    s(), finite("owed|paid|gave|promised", "ditransitive"), obj(), noun("money|gold|payment|silver"),
    COMMA, s(), lx("did", "AUX"), COMMA, AND, finite("took|brought|carried", "transitive"),
    possess("knife|bag|letter|book|coat|watch"), adv("ashore|aboard|away|home"),
    pp("with"), obj(), STOP, CLOSE, speech=True)

REPEATED_EXCLAMATION = "dialogue_structural_repeated_interjection_then_question_and_manner_report"
define(REPEATED_EXCLAMATION, 2, OPEN, OH, scoped("dear me|my goodness", "INTERJECTION"),
    COMMA, scoped("dear me|my goodness", "INTERJECTION"), COMMA, lx("do|did", "AUX"),
    s(), base("think|suppose|believe|imagine", "clausal"),
    s(), modal("will|would|could|might"), scoped("do|bring|give", "V", vform="base", subcat="ditransitive"), obj(),
    det("any|some"), noun("good|harm|comfort|relief|pleasure"), QMARK, CLOSE, REPORT_INTRO,
    possess("mother|father|aunt|uncle|sister|brother|friend"), pp("in"), det("a|an"),
    adj("helpless|anxious|worried|agitated|urgent"), noun("manner|voice|tone"), STOP, speech=True)

THANKS_WITH_RESUMPTION = "dialogue_structural_vocative_thanks_reporting_gesture_and_repeated_title"
define(THANKS_WITH_RESUMPTION, 3, OPEN, base("Thank|Bless", "transitive"), obj("you"), COMMA,
    scoped("Master|Miss|Captain|Doctor", "TITLE", honorific="true"), name(), COMMA, CLOSE,
    scoped("returned|replied|answered", "V", vform="finite", subcat="clausal"), name(), COMMA,
    ing("putting|placing|laying|setting", "transitive"), possess("book|letter|papers|coat|cup"), adv("away|down|back"),
    pp("upon|on|into"), nom(r"the +(?:shelf|table|desk|bench|case|box)", "np_det_n"), DASH, OPEN,
    s(), finite("suppose|think|believe|imagine", "clausal"), s(), finite("stop|stay|remain|wait", "intransitive"),
    adv("here|there"), COMMA, det("some|a little"), noun("time|while"), COMMA,
    scoped("Master|Miss|Captain|Doctor", "TITLE", honorific="true"), name(), QMARK, CLOSE, speech=True)

HEIGHT_CORRECTION = "dialogue_structural_elliptical_prediction_and_genitive_height_correction"
define(HEIGHT_CORRECTION, 3, OPEN, s(), finite("think|suppose|believe", "clausal"),
    s(), modal("will|would|could|might"), STOP, s(), COP_PRESENT, adv("now|already|still"),
    scoped("about|nearly|almost", "DEGREE", approximative="true"),
    scoped("Miss|Master|Mrs|Mr", "TITLE", honorific="true"), name(r"[A-Z][a-z]+ +[A-Z][a-z]+"),
    lx("[’']s", "POSS", genitive_clitic="true"), noun("height|size|weight|age"),
    COMMA, lx("or", "COORD"), degree("rather"), scoped("taller|shorter|larger|smaller|older|younger|heavier|lighter", "ADJ", comparative="true"),
    STOP, CLOSE, speech=True)

GERUND_ADVICE = "dialogue_structural_conditional_advice_and_negated_reminder_with_gerunds"
define(GERUND_ADVICE, 3, OPEN, adv("Perhaps|Maybe|Possibly"), scoped("it", "EXPL"), modal("will|would|might"),
    BE_BASE, scoped("as well|better|best", "ADJ"), conjunction("if"), s(),
    finite("discourage|prevent|stop|oppose", "transitive"), POS,
    ing("coming|going|calling|visiting|returning", "intransitive"), adv("here|there"),
    degree("so"), degree("very"), adv("often|frequently|regularly"), STOP,
    scoped("At least|In any case", "ADV"), COMMA, s(), modal("should|could|must"), NOT,
    base("remind|warn|accuse", "transitive"), possess("mother|father|aunt|uncle|friend|sister"),
    OF, ing("inviting|asking|encouraging|welcoming", "transitive"), obj(), STOP, CLOSE, speech=True)

LOCATIVE_RECOLLECTION = "structural_negative_copular_location_with_coordinated_proximity_and_regret_relative"
define(LOCATIVE_RECOLLECTION, 2, adv("Thoughtfully|Silently|Sadly|Quietly"), COMMA, lx("for", "COORD"),
    s(), modal("could|would|might"), NOT, BE_BASE, adv("here|there"),
    scoped("once more|once again|yet again", "ADV"), COMMA, AND, degree("so|very"), pp("near|beside"), name(),
    COMMA, pp("without"), det("the"), noun("revival|return|recurrence|renewal"), OF,
    det("those|the"), noun("regrets|thoughts|memories|anxieties|concerns"),
    pp("with|by"), RELATIVE, s(), HAD, degree("so|very"), adv("long"), lx("been", "AUX-BE", vform="ed"),
    participle("occupied|concerned|troubled|absorbed|preoccupied", "transitive"), STOP)

HEIGHT_PERFECT = "structural_epistemic_modal_with_inner_perfect_and_scalar_measure"
define(HEIGHT_PERFECT, 2, s(), modal("should|would|could"), base("think|guess|suppose|believe|reckon", "clausal"),
    s(), modal("must|might|could|may"), BASE_HAVE, PERTINENT_COP,
    scoped("as much as|as many as|about|nearly|almost", "DEGREE", extent_marker="true"),
    lx(NUMERAL, "NUM"), noun("feet|metres|meters|inches|yards"), adj("high|tall|wide|long|deep"), STOP)

SHIVER_REPORT = "dialogue_structural_minor_shivering_report_with_shared_participles_and_bare_causative"
define(SHIVER_REPORT, 1, OPEN, scoped("All", "DEGREE", total_degree="true"), OF, det("a"),
    noun("shiver|tremble|quiver|flutter"), COMMA, CLOSE, REPORT_INTRO, name(TITLE_NAME),
    COMMA, ing("counterfeiting|imitating|mimicking|feigning", "transitive"),
    nom(r"that +(?:affection|condition|expression|habit|movement)", "np_det_n"), AND,
    scoped("making", "V", vform="ing", subcat="causative"), possess("teeth|hands|lips|arms|fingers"),
    base("chatter|shake|tremble|rattle|quiver|move", "intransitive"), STOP, speech=True)

TOUCH_DELIGHT = "structural_negative_declaration_then_degree_result_with_motion"
define(TOUCH_DELIGHT, 4, s(), finite("declared|insisted|said|announced|stated", "clausal"), CONTENT_THAT,
    scoped("nobody else|no one else|no-one else", "PRONOUN", negation="true"), modal("should|could|would|must"),
    base("touch|take|move|disturb|use|read", "transitive"), obj(), SEMI, AND, DEMONSTRATIVE,
    finite("gave|brought|afforded", "ditransitive"), name(), degree("such"), noun("delight|joy|comfort|relief"),
    CONTENT_THAT, s(), finite("went|walked|ran|hurried", "intransitive"),
    adv("away|home|out|off"), pp("in"), adj("good|high|bright|better|excellent"), noun("spirits|humour|humor"), STOP)

POSTURE_ABSOLUTES = "structural_progressive_posture_with_paired_partitive_and_locative_absolutes"
define(POSTURE_ABSOLUTES, 1, s(), PAST_BE, ing("standing|sitting|kneeling|waiting", "intransitive"), adv("close"),
    pp("beside|behind|before"), obj(), COMMA, pp("with"), lx("one", "NUM"), OF, POS,
    scoped("skeleton|bare|thin|bony|cold", "ADJ"), noun("hands|arms|fingers"), pp("over|against"), possess("mouth|head|face|cheek"),
    COMMA, AND, det("the"), scoped("other", "PRONOUN", partitive_other="true"), ing("resting|lying|leaning", "prepositional"),
    pp("on|against"), det("the"), noun("[Dd]octor|[Cc]aptain|[Tt]eacher|[Pp]rofessor"),
    lx("[’']s", "POSS", genitive_clitic="true"), noun("table|desk|bench|chair"), STOP)

ABSOLUTE_CHRONOLOGY = "structural_framed_perfect_then_shared_subject_progressive_and_temporal_call"
define(ABSOLUTE_CHRONOLOGY, 3, pp("After|Before"), noun("breakfast|lunch|tea|dinner|supper"), COMMA,
    scoped("the next morning|the following morning|the next day|the following day", "ADV", relative_day="true"),
    COMMA, s(), HAD, scoped("put|placed|set|pushed", "V", vform="ed", subcat="transitive"),
    possess("chair|book|pen|table|coat|hat|baggage"), adv("away|aside|down|back"), COMMA, AND,
    PAST_BE, ing("going|walking|stepping|moving", "prepositional"),
    scoped("out of|away from|through", "PREP", path="true"), nom(r"the +(?:room|hall|house|chamber|cabin)", "np_det_n"),
    COMMA, conjunction("when"), name(TITLE_NAME), finite("called|summoned|sent|drew|beckoned", "transitive"),
    obj(), adv("back|inside|over|away"), STOP)

HIRED_PAGE = "structural_hired_person_depictive_with_predecimal_salary_and_copular_consequence"
define(HIRED_PAGE, 2, det("This|That|The"), adj("unlucky|unfortunate|unhappy|promising|young"), noun("page|servant|apprentice|clerk|boy"),
    COMMA, participle("engaged|hired|employed|appointed", "transitive"), pp("in"), det("an|a"),
    adj("evil|unlucky|happy|bad|fortunate|dark"), noun("hour|moment"), pp("at"),
    lx(NUMERAL, "NUM"), noun("pounds"), lx(NUMERAL, "NUM"), scoped("per annum|per year|a year", "ADV", pay_period="true"), COMMA,
    COP_PAST, det("a"), noun("source|cause|fountain"), OF, adj("continual|continuing|constant|frequent|much"),
    noun("trouble|pain|pleasure|delight|annoyance"), pp("to|for"), obj(), STOP)

PLAN_LOCATION = "structural_infinitival_plan_with_nested_locations_and_habitual_existential_relative"
define(PLAN_LOCATION, 2, scoped("This|That", "DEMONSTRATIVE-PRONOUN", deictic="true"), COP_PAST,
    COMMA, TO, base("lie|stand|wait|remain|stay", "intransitive"), pp("behind|before|beside"),
    det("the"), noun("wall|fence|hedge|gate|building"), pp("at|near"), det("the"), noun("back|front|side"), OF,
    POS, adj("old|former|new|little|first"), noun("school|house|home|cottage|room"), COMMA,
    pp("in|at"), det("a"), noun("corner|place|spot|patch"), lx("where", "WH-NOM"), lx("there", "EXPL"),
    scoped("used", "HABITUAL-AUX", vform="finite"), TO, BE_BASE, nom(r"an? +(?:haystack|tree|shed|bench|orchard|stall)", "np_det_n"), STOP)

IMAGINED_ATTENTION = "structural_reflexive_perception_predication_with_coordinated_unfamiliar_audience"
define(IMAGINED_ATTENTION, 1, s(), finite("saw|imagined|pictured|found|fancied", "transitive"),
    lx("herself|himself|themselves|myself|ourselves", "PRONOUN"), det("the"),
    noun("object|centre|center|focus|subject"), OF, noun("attention|admiration|interest|curiosity|praise"),
    COMMA, pp("to"), noun("tens|dozens|scores|hundreds"), AND, pp("to"), noun("scores|hundreds|thousands|dozens|tens"), OF,
    obj("them|us"), scoped("at present|right now|for now", "ADV", temporal="true"),
    adj("unknown|unfamiliar|unidentified|unrecognised|unrecognized"), STOP)

LONGING_AND_RESTRAINT = "structural_controlled_desire_perfect_copula_and_consecutive_elliptical_supplement"
define(LONGING_AND_RESTRAINT, 4, name(), finite("longed|wished|wanted|yearned|hoped", "subject_control"),
    TO, base("observe|say|remark|declare|add|mention", "clausal"), CONTENT_THAT, name(TITLE_NAME),
    HAD, PERTINENT_COP, det("a"), scoped("most|very|truly|especially", "DEGREE"), adj("delightful|helpful|wonderful|charming|agreeable"),
    noun("friend|companion|guest|neighbour|neighbor|ally"), SEMI, degree("so"), adv("easily|readily|quickly"),
    participle("guided|led|influenced|persuaded|directed", "transitive"), CONTENT_THAT, possess("worth|value|help|assistance"),
    COP_PAST, adj("invaluable|indispensable|immense|incalculable"), SEMI, BUT,
    s(), finite("checked|restrained|stopped|controlled", "transitive"), lx("herself|himself|themselves", "PRONOUN"), STOP)

STRANDED_MORNING = "structural_time_description_with_stranded_relative_and_dash_elaboration"
define(STRANDED_MORNING, 4, scoped("It", "EXPL"), COP_PAST, adv("still"), degree("quite|rather|very"),
    adj("early|late|dark|quiet"), COMMA, AND, det("the"), scoped("coldest|hottest|darkest|longest|dampest", "ADJ", superlative="true"),
    noun("morning|night|evening|day"), RELATIVE, s(), finite("think|believe|suppose|remember", "clausal"),
    s(), adv("ever"), COP_PAST, adv("abroad|outside|out|awake"), pp("in"), DASH, det("a|an"),
    noun("chill|cold|heat|wind|silence"), RELATIVE, scoped("pierced|cut|spread|reached", "V", vform="finite", subcat="prepositional"),
    pp("into|through|to"), nom(r"the +(?:marrow|bone|bones|walls|skin|room)", "np_det_n"), STOP)
