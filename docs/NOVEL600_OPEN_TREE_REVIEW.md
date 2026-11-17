# Novel-600 — source review for the 55 open trees

This is an attachment checklist for the cases still marked `needs_fix` on
PR #97 at `4add4b6ce47bf62c48eaaed2a9e96f0abef8a16a`. It is **not** a new parser run, a new
review verdict, or an accepted benchmark. At that point the result was
100 complete selected trees, 45 verified and 55 requiring work. The
[follow-up attachment pass](NOVEL600_ATTACHMENT_PASS.md) records the
subsequent replay and the remaining cases.

The SHA-256 of each of the four source editions and all 100 frozen source
slices was checked against the [cohort manifest](../superparser/research/novel_ladder/novel-600-cohort.json).
The stored tree and graph digests in the [review ledger](../superparser/research/novel_ladder/novel-600-review.json)
matched the [current signature file](../superparser/research/novel_ladder/novel-600-current.json)
for all 100 entries. Those integrity checks do not establish that the
selected trees are linguistically correct. The checklist below was read
against the exact source paragraphs. Offsets are half-open Unicode
character spans in the cleaned book unless marked local.

## Next in the queue — N510

> I performed the first part of my journey on horseback.

The following sentence switches to a mule. That contrast makes the
locomotion reading concrete. The prior rank-one tree attaches the modifier
at the right level but selects `vp_adv_adj` and `advp_particle_adv` for
`on horseback`. Its graph exports MANNER from `performed` to the particle
`on` alone. This is a category and role error even though the tree covers
the sentence and the modifier is attached to the VP.

| Witness | Local span | What the replacement must preserve |
| --- | --- | --- |
| `I` | `[0, 1)` | Subject and agent of the finite predicate |
| `performed` | `[2, 11)` | Matrix event, not part of the object |
| `the first part of my journey` | `[12, 40)` | Full object, headed by `part` with the ordinal and genuine part-whole dependency inside it |
| `on horseback` | `[41, 53)` | Means or manner of performing, with a preposition `on` at `[41, 43)` and its complement at `[44, 53)` |
| `.` | `[53, 54)` | Original full stop remains in the source |

An independent positive is “We covered the first stage of our trip on
horseback.” A near miss is “We pushed on toward the pass.” The latter
has a true verb particle and must not select the horseback composition.
A separate nominal control is “A photograph of a rider on horseback hung
in the hall.” The final phrase inside the subject NP must not be attached
to `hung`. Keep the original lexical alternatives and only prefer a
new PP analysis where its lexical evidence and attachment are justified.

## Reproduce just the trees needed for inspection

Set `WORDNET_DICT` to the usual WordNet 3.0 dictionary. From the repository
root, the following uses the existing frozen resolver and `measure` helper,
which calls `parse_corpus_case` with 50,000 chart items, 500,000 k-best work
units and a 10-second deadline. It writes the exact source, typed
constituents, rank-one tree, semantic graph and comparison signature. This
command is a targeted inspection recipe. It does not replace the full
cohort replay after a grammar change.

```sh
PYTHONPATH=superparser python - 510 514 > /tmp/novel600-selected.jsonl <<'PY'
import json
import os
import signal
import sys
from pathlib import Path

from scripts.evaluate_novel_transfer import MAX_ITEMS, ROOT, _deadline, measure
from scripts.novel_ladder import LADDER, load_sources, read_ladder, signatures
from seman_parser.engine import Parser, ParserResources

wanted = set(map(int, sys.argv[1:]))
if not wanted:
    raise SystemExit("Provide at least one frozen Novel Ladder index.")
cohorts, _, _ = read_ladder(LADDER, load_sources())
by_index = {case["ladder_index"]: case for _, cases in cohorts for case in cases}
missing = wanted - by_index.keys()
if missing:
    raise SystemExit(f"Unknown frozen indices: {sorted(missing)}")
wordnet = Path(os.environ["WORDNET_DICT"])
parser = Parser(ParserResources.from_dir(ROOT / "data", wordnet_dict=wordnet),
                cache_size=0, max_items=MAX_ITEMS)
parser.parse("John opened the box.")
handler = signal.signal(signal.SIGALRM, _deadline)
try:
    for index in sorted(wanted):
        row = {**by_index[index], **measure(parser, by_index[index], with_semantics=True)}
        print(json.dumps({**row, "signature": signatures([row])[0]}, ensure_ascii=False))
finally:
    signal.signal(signal.SIGALRM, handler)
PY
```

## Attachment checks in queue order

These are acceptance conditions to check on actual rank-one output. Where
several analyses fit, preserve the alternative and test the contrast rather
than turning a preference into a rule that makes the other reading
impossible. The existing saturation flags on N547 and N575 are separate
from the attachment verdicts.

### Frankenstein

| Case and source span | Keep in the selected analysis | Counter-reading to check |
| --- | --- | --- |
| N510 `[158070, 158124)` | Keep `I` as subject of `performed`, `the first part of my journey` as object, and `of my journey` inside the object. `on horseback` is a means/manner PP of the performance, with `on` and its complement in the same span. | Do not export `on` by itself as the manner. Do not attach the PP to `journey` or recategorize it as a verbal particle. |
| N514 `[288236, 288339)` | `We` controls the subject of `commence` through `determined`. `our journey` is its object and `towards the north` characterizes that journey or its direction of travel. The one-month endpoint times commencement. | Do not date the act of deciding with the one-month endpoint or make the journey the controller. |
| N517 `[258739, 258825)` | `The being` is the subject of both `finished` and `fixed` and the understood speaker in `speaking`. `upon me` is the target of his directed look. `in the expectation of a reply` gives the circumstance of fixing the look, with `of a reply` inside the expectation phrase. | Do not read the expectation as a recipient or as the second finite predicate’s subject. |
| N518 `[268461, 268562)` | `My haggard and wild appearance` is one subject of `awoke`, with `intense alarm` as object. The contrast introduces `I answered no question`. The comma introduces a third clause with `scarcely` and its own inverted `did I speak`. | Do not lose the first finite event or promote `appearance` to a topic of `answered`. Do not make the last clause a complement of `question`. |
| N519 `[29809, 29903)` | `told` selects `me` as recipient and the overt `that` clause as content. Inside it, `would` scopes over `commence`, `the next day` dates commencement, and the `when` relative identifies that day by the narrator’s availability. `then` independently times the telling. | Do not attach tomorrow or the availability clause to the telling. Do not merge the two occurrences of `he` with the recipient. |
| N521 `[335542, 335661)` | `talked` governs both `of Geneva` and `of Elizabeth and Ernest`. `which I should soon visit` supplements `Geneva` and has a visit-object gap. `but` introduces `these words` as a new subject of `drew`. | Do not make Geneva a topic of `drew`, attach the relative to the second `of` phrase, or take the people as visitors. |
| N524 `[261948, 262074)` | `when I thought ...` is an adjunct timing `shuddered`. Its `of the possible consequences` belongs to `thought`, with `of my consent` inside `consequences`. The `that` existential clause is the content of the distinct second predicate `felt`. | Do not recast `when` as a selected interrogative or attach the justice clause to `thought`. |
| N525 `[26625, 26764)` | The sky, sea and every sight coordinate as the subject of `seem`. `afforded by these wonderful regions` is a reduced passive relative on `every sight` only. `still` expresses persistence of the seeming or continuing capacity. The full infinitival predicate has the capacity with its gerund complement. | Do not make `still` an object or give the reduced relative the whole coordination as antecedent. |

### Treasure Island

| Case and source span | Keep in the selected analysis | Counter-reading to check |
| --- | --- | --- |
| N528 `[285045, 285074)` | `Avast` is a nautical interruption or command in the quoted act. `there` stays inside the call, and the inverted report makes Silver the speaker of that act. | Do not treat `Avast` as a name or treat `there` as the reporter's location. |
| N529 `[222860, 222893)` | `Certainly` is epistemic stance over the negative proposition `I did not know her way`. `did` carries tense, `not` negates `know`, and `her way` is its object. | Do not export stance as topic or omit the negation edge on knowing. |
| N531 `[346463, 346509)` | The opening salute PP frames or triggers `flushed`; `Silver's` and `polite` modify the salute. `somewhat` grades the flushing rather than naming an independent event. | Do not turn the salute into a topic or `somewhat` into a participant. |
| N532 `[148106, 148172)` | `perked up` is a particle predicate. `at my last words` frames the reaction and `into` introduces the resulting state. Under that PP, `a kind` is the nominal head and `of startled slyness` its complement. | Do not promote `kind of` to a free degree marker of `perked` or treat `up` as the head of the result PP. |
| N533 `[274209, 274283)` | Use existential `there`, with the negated, coordinated pivot `a soul stirring` and `a sound`. `stirring` qualifies `soul`. The context favors an exception for sounds, because the breeze explains the audible exception and not an exception to the absence of people. | Test narrow attachment to `sound` against wide exceptive scope rather than equating them. Neither reading makes `beside` an ordinary location for the existential. |
| N535 `[197803, 197842)` | `It` is anticipatory. `to see them` is the extraposed evaluation content. `as good as the play` is the predicative comparison, where `the play` is the benchmark and `them` the object of seeing the men. | Do not attach the infinitive to `play` as a nominal modifier or give it to `good` as a purpose. |
| N536 `[284937, 284980)` | `Then here goes!` is one quoted act attributed to Morgan. `with an oath` is a circumstance or manner of `said`, and it remains outside the quote. | Do not make the oath an object, recipient or part of the spoken text. |
| N537 `[129436, 129503)` | Separate anticipatory cleft `it` from focused `we of the cabin party`. `who` supplies the subject of `perceived`, bound to that focus. `not only` scopes the focus, consistent with others also perceiving the danger. | Do not negate the danger perception outright or use `it` as the perceiver. |
| N538 `[54124, 54164)` | There are two minor speech acts, confirmation `To be sure` and evaluation `quite right`, with the vocative `boy` in the first. `said he` attributes the whole quote. The semicolon is inside the speech. | Do not restore unspoken finite subjects, reinterpret `boy` as an argument, or split at the semicolon. |
| N539 `[27810, 27923)` | `as things fell out` frames the narrative. The death happens `that evening` and `quite suddenly` modifies `died`. `which` refers to that death event. `put all other matters on one side` is a result construction, supported by the narrator’s ensuing obligations. | Do not choose `evening` as the antecedent or treat `on one side` as an unrelated narrator location. |
| N540 `[59878, 59974)` | Keep the `if Jim is agreeable` condition inside the spoken future about opening the packet. The act of laying it is subsequent narrative. `on the table` is the result location of laying, and `before him` is its spatial orientation. | Do not extend the speech condition to the actual laying or treat `him` as the object being laid. |
| N542 `[251048, 251133)` | Keep three predicates inside the quote. `not` scopes over `strong enough`, `don't` over `like`, and `there he lies, for me` is its own clause with a local stance/circumstantial supplement. The tag attributes the whole turn to `I`. | Do not bind `don't` to a pronoun, attach `for me` to `like`, or turn deictic `there` into an existential subject. |
| N544 `[75839, 75931)` | Keep three literal semicolon-linked finite clauses. `was ... painted` and `was ... sanded` are passives with separate subjects. `newly` modifies painting and `cleanly` sanding. `had` takes `neat red curtains` as object. | Do not reinterpret the two V-en participles as unlinked nouns or lose the middle finite clause. |
| N545 `[142479, 142620)` | `I` controls both `extricate` and `crawl` under the single `began`. `myself` is the reflexive object of extricating. The named destination belongs to crawling, and `with what speed and silence I could manage` is the manner supplement to the retreat. | Do not promote the supplement or destination to matrix coordination or make `myself` the agent of crawling independently of `I`. |
| N546 `[171184, 171313)` | Separate the stores existential and the remaining-guns clause. `to make things worse` is a metacomment prefacing the second assertion. `only` qualifies the two-out-of-five quantity, with `in a state for service` predicated of the surviving guns. | Do not attach `worse` to `guns`, treat `for service` as a new purpose of the speaker, or interpret `out of five` spatially. |
| N547 `[106067, 106212)` | `imagine` takes the embedded `how I felt` question. The hearing times feeling. The rogue is the object of heard and the understood subject of addressing another. The same-words comparison specifies the language used in addressing. | Do not move the comparison onto hearing or make `as he had used ...` a separate matrix clause. The pre-existing forest flag does not validate any reading. |
| N549 `[170289, 170412)` | `had never so much as looked` is negative perfect with an emphatic minimum. `though he was not dead` is concessive around the lack of attention. The second matrix subject `I` sees him trying to crawl away, with `him` the one trying. | Do not turn the concessive into a condition on seeing or transfer perfect negation to the second clause. |
| N550 `[30891, 31020)` | `so much startled` licenses the result clause about struggling to withdraw. `I` controls withdrawal. In the contrasted pulling clause, `with a single action of his arm` specifies how the blind man pulled, with `of his arm` local to the action. | Do not attach the result to pulling or label the single action a recipient. |

### David Copperfield

| Case and source span | Keep in the selected analysis | Counter-reading to check |
| --- | --- | --- |
| N554 `[275690, 275722)` | `No` is a complete negative response and `father` its vocative. `Minnie interposed` is an overt, postposed attribution, with Minnie as subject. Check recognizer licensing of the reporting span before adding grammar. | Do not insert a finite predicate inside the quote or treat `father` as the speaker. Do not change the source span to sidestep the tag. |
| N555 `[1327362, 1327379)` | Keep the elliptical predicate question `Cross?`, with `my love` as vocative. The preceding dialogue supplies the relevant meaning of `cross` as an adjective and supports an omitted second-person subject. | Do not promote `my love` to the subject, select a crossing command or manufacture omitted words. |
| N556 `[851629, 851649)` | Read `the Arches` as the name of a court, confirmed by the very next sentence. Preserve the nominal wh question with an overt copula and a question force link. | Do not select common plural arches as a physical-object answer or reinterpret the singular `was` as a new predicate. |
| N557 `[1245413, 1245443)` | `of it` is the complement of the predicative adjective `sure`, not a generic topic. Preserve the independently sourced report with Agnes as speaker and the quoted clause as content. | Do not make the PP an argument of `said` or invent what `it` refers to in Layer 1. |
| N560 `[513175, 513251)` | Keep `Uriah Heep` together as reporter and `Master Copperfield` together as the addressed person. `at present` qualifies the reported state, and `of glory` belongs inside `partaker of glory`. | Do not make `Heep` a speech object or `Copperfield` the person described in the quoted predication. |
| N561 `[722598, 722644)` | `you` is the explicit object of `believe`. `my pet` is a detached vocative. `Miss Mowcher` is one reporting subject of `replied` and the reporter is separate from the quoted first-person clause. | Do not append the vocative to the belief object or parse `Mowcher` as a recipient. |
| N562 `[237188, 237252)` | `Then` times the action sequence. Both kissed and clasped have the same overt subject `she`, and each has overt object `me`. `more and more` modifies kissing, while `round the neck` locates the clasping. | Do not put the clasping location inside the pronoun NP or leave the second predicate without its agent. |
| N563 `[1253850, 1253937)` | `looking` is embedded predication about `him` under `thought`. `as ever` is the equative standard of `as villainous`. The explicit second `I` introduces an independent `replied` clause with its own content `that I saw no change in him`. | Do not let `looking` describe the observer or put the reply inside the thought complement. |
| N564 `[673403, 673487)` | `no` scopes over `misgiving`, with the `that` proposition as its content. Inside that proposition, `it` anticipates `to respond to her emotions`, which is evaluated as `young in me`. The first-person participant controls the response. | Do not let the outer negative quantifier `no` negate or assert the actual responding. Do not make `her emotions` the response’s agent. |
| N565 `[790106, 790198)` | All three predicative descriptions share one `he` in the content of `said`. The overt final `and` and the toast context favor a coordinated list, with no additional people. `of my boyhood` and `of my prime` are local relations of protector and companion, not part-whole. | If retaining an appositional alternative, require the same co-predication and local `of` links. Do not invent a separate matrix predication for each noun. |
| N567 `[585945, 586017)` | Keep `a summer evening` as temporal scene-setting. `down in a green hollow` and `at the corner of a wall` locate the scene of the meeting, with the second phrase giving the finer location. `of a wall` remains local to `corner`. | Do not coordinate `wall` as a clause or treat the time itself as the physical object placed in the hollow. |
| N568 `[1068023, 1068122)` | `that I knew of` is a relative on `question`, with `of` stranded and its gap linked to `question`. `in the world` gives the scope of the no-other-question assertion, possibly via the embedded knowing frame. In the independent second clause `only` focuses `Dora`. | Do not recover a missing object by inventing words or attach the restriction `only` to the answer or question. |
| N569 `[607898, 607985)` | The fronted NP `The expression of her face` is the object of `felt` and understood subject of `to be very touching`. The `as` incise temporally frames the perceiving situation and has its own plural subject `they`. | Do not turn the expression into a bare topic or the incise into a coordinated matrix clause. |
| N570 `[147405, 147516)` | Keep four spoken attempts with their exact dashes, changing subject from `you` to `I` before the final completed question. `what` asks the amount to pay, not the identity of the waiter. `the waiter` is the payee within `to pay`; `if you please` is a politeness supplement to the question. | Do not fill predicates of interrupted attempts or insert the addressee as the subject of the final extraposed construction. |
| N573 `[1271584, 1271709)` | Preserve the negative knowledge report and the embedded perfect `have done`. The phrase `in my fatuity` is plausibly a retrospective comment on his actions, supported by the ensuing confession, but the comma also supports higher speaker stance. Keep the report and its gestural supplement outside the quote. | Do not certify uniqueness of attachment without contrasting the two readings. Do not lose perfect aspect or make the reporter’s gesture part of the spoken content. |
| N575 `[1136355, 1136487)` | The fox is the causer and the overt object `him` supplies the agent of `say`. The purpose `to exhibit him to me` belongs to the causer’s action, with `I knew` as evidential incise. The `when` clause modifies `night`, which places the indicated description in prior time. | Do not attach the purpose to saying alone or `I knew`. The existing forest flag is not evidence that these dependencies survived. |

### Pride and Prejudice

| Case and source span | Keep in the selected analysis | Counter-reading to check |
| --- | --- | --- |
| N581 `[126823, 126852)` | `It` resumes the interval of waiting. `over` is its predicative finished state, `at last` times the ending and `however` marks a discourse contrast. | Do not export `over` as location or make the discourse adverb the temporal modifier. |
| N582 `[399697, 399744)` | `would` scopes over the particle verb `set ... up`, meaning to revive or restore. `me` is the affected person, `A little sea-bathing` the cause and `forever` the duration of the projected result. | Do not read `up` as a free manner adjunct or interpret `forever` as duration of the bathing. |
| N584 `[45119, 45187)` | The condition frames the matrix obligation or commitment. `I` controls `to be always sensible`; `always` modifies the state and `of it` is the adjective’s complement. `hope` takes the full infinitive. | Do not take `of it` as an argument of `hope` or attach the condition only to `sensible`. |
| N585 `[528983, 529027)` | Keep the interrogative modal order with overt copula and adjective `possible`. `it` anticipates the proposition `that he will marry her`, with `will` scoped inside that proposition. | Do not turn `possible` into a nominal head or make the embedded marriage the outer question’s finite predicate. |
| N586 `[383665, 383720)` | `She` is the subject of the evaluative copula and the understood agent of the verbal gerund `going away`. `for` gives the ground of the evaluation, while `if she liked him` conditions the criticism. | Do not select an event noun that loses the agent or infer that her liking him is independently asserted. |
| N587 `[364622, 364674)` | `Widely different` is a fronted predicative adjective phrase whose subject follows the copula. `widely` grades difference. The second reading explains the effect and the source context contrasts it with the first. | Do not promote `widely different` to a nominal subject or omit the copula/subject/attribute dependency. |
| N589 `[81652, 81775)` | `Miss Bingley` is one subject of `resented`, `warmly` modifies resenting and the indignity is its object. The indignity is also the relativized object of `received`, with `had` as perfect auxiliary. `for talking such nonsense` gives the ground of the expostulation with her brother. | Do not terminate the name at `Miss` or count the relative as correct while dropping its perfect auxiliary. |
| N590 `[287529, 287624)` | Keep two separate wh questions and a last inference under `must have been neglected`. `who` is subject of each question, and the second contains `attended to you`. `without a governess` supplies the premise of the inference. The last clause is modal, perfect and passive. | Do not use genuine question marks as nominal-relative separators or attach the last passive to either wh question. |
| N591 `[338808, 338913)` | `the park paling` is the subject of the first copular clause, with `the boundary on one side` as predication and `still` as persistence. In the second clause `she` passes one gate out of a plurality, and `into the ground` gives her direction of movement. | Do not duplicate `gates` as two heads or attach the direction to the gates themselves. |
| N592 `[359269, 359360)` | The initial `Of his former way of life` sets the domain for what is known. `nothing` is the overt subject of the perfect passive `had been known`; `in Hertfordshire` locates that knowledge. `but what he told himself` is an exception containing a free relative. | Do not coordinate Hertfordshire and the free relative as NPs. Avoid treating `himself` as the recipient unless the context supports self-telling. The surrounding paragraph favors emphatic `he himself` as source. |
| N593 `[487428, 487533)` | The long negative-consequence NP is dislocated and resumed by `it` as the object of `feel`. `oh` is a separate interjection. `how acutely` grades feeling in the inverted exclamative and `now` times that feeling. | Do not treat the inversion as an information question or sever `it` from the dislocated topic. |
| N594 `[164608, 164719)` | The quote contains a free-relative copular statement, the independent reaction `I am satisfied`, and a separate wh question. In the first clause `what` is the received item and `from Mr. Darcy` marks source. In the final question `of the living` is the topic of saying. | Do not consume inter-sentence punctuation in a single apposition or promote the narrator’s satisfaction to a modifier of the account. |
| N596 `[58607, 58739)` | The initial gerund phrase characterizes the activity in which the addressee takes pleasure, inside the proposition of which Bingley is sure. The tag `said Bingley` is outside the two spoken parts. In the second, `by seeing her quite well` supplies the means or cause of the pleasure increasing, under hope. | Do not attach nursing or seeing to `said`. Do not turn `her quite well` into merely a manner of seeing, or assert that the hoped increase already happened. |

## Closeout after a real replay

1. Review both the selected syntax and the exported graph against these
   checks. Save concrete span and role evidence and the two observed
   digests for each verified case.
2. For any code change, require the source case, an independent positive,
   and a near miss. Show that any other changed selected output is
   intentional. Recheck the complete frozen Novel-600 lot, the historical
   Novel-500 signatures and dialogue-30 at unchanged budgets.
3. Keep unresolved cases open. Do not count a complete root, a candidate
   tree below rank one, or a matching checksum as a grammar correction.
   Leave Novel-700 closed until Novel-600 has 100 verified selected analyses.
