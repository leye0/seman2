# Semantic quality findings: Novel-700 + exploratory Novel-800

**Not a certification.** This is a source-grounded review of actual selected
rank-one trees and semantic graph edges from the frozen full-replay artifacts,
not a score inferred from `completed` or stable SHA-256s.

Source evidence:
- Novel-700: [final full replay](https://github.com/leye0/seman2/actions/runs/44167834185)
- Novel-800: [final full replay](https://github.com/leye0/seman2/actions/runs/44173694683)
- Same original text, source offsets, WordNet 3.0 and 50k/500k/10s limits.

At the start of the audit, **76 Novel-700** and **85 Novel-800**
complete analyses lack individual attachment reviews. Existing verdicts
are not overwritten and the original frozen sources/results are unchanged.

## Confirmed problems in the selected outputs

Each row lists an **actual lexical reading or graph edge** in the selected
result, followed by the grammatical distinction to recover.
These are faults of the chosen rank-one output, not merely potentially
better alternatives. Cases below must **not** be relabelled `verified`
until a correct selected tree and graph, an independent positive, a relevant
negative, and preserved predecessor signatures are demonstrated.

| Source ID | Selected-tree / semantic defect | Required attachment or reading |
| --- | --- | --- |
| N601 | `not` is a NEGATION node without an incident edge; `answer` has AGENT and MODALITY only | Negation must scope over ability/answering |
| N605 | `roughly` is attached to auxiliary `do` rather than lexical `answer` | Degree/manner of answering; interrogative reason attached to question predicate |
| N607 | `RECIPIENT(took, Elizabeth)` from `the hand of Elizabeth` | Elizabeth belongs to the hand's possessor relation, not recipient of taking |
| N608 | A complete 60-character selected modal-relative question has **zero graph edges** | Subject of `allude`, modal `Could`, object PP and relative/negative `dared not think` |
| N610 | `In this` is read as ADV and `AGENT(find, house)` | `In this house` is a locative PP; `I` is subject of `chanced` and controller of `find` |
| N613 | `to reply` is selected with `reply` as N, not infinitival predicate | `unable` governs a verbal infinitive `to reply` |
| N620 | `in` is selected as PARTICLE in `spent in listless indolence`; `AGENT(spent, days)` | Proper locative/manner PP and passive/reduced-relative relation of days spent |
| N626 | `No` treated as noun in `"No, sir"` with `APPOSITION(No, sir)` | Negative reply, vocative sir, actual speech attribution |
| N629 | `AGENT(moved, as)`; `never` selected DEGREE without negation scope | `the doctor` is agent/subject of `moved`; `never so much as` negates/minimizes event |
| N631 | `That was the ship's mystery` has no selected possessor link ship→mystery | `ship's` attaches as genitive modifier of mystery |
| N633 | `like` in idiomatic `as like as not` is chosen as transitive V with `AGENT(like, knife)` | Parenthetical epistemic likelihood idiom, not a new lexical liking event |
| N635 | `cap'n` is split as `cap` V + `'n` N, producing `AFFECTED(cap, n)` | Original dialectal vocative `cap'n`; no cap-verb event |
| N636 | `won't` becomes `won` (V, win) + `'t` negation and `AFFECTED(won,you)` | Contracted will-not tag question, not an event of winning |
| N637 | `Here` becomes N, `AGENT(come, Here)`, `AFFECTED(come,gigs)` | Inverted existential/deictic `Here come the gigs`: `gigs` subject, `Here` locative; sir vocative |
| N638 | Reported directive `take that, and stand by` has only reporter AGENT and take-object relation | Both imperative predicates, their coordination, and reporter→content link |
| N644 | `stay` is N and `AGENT(exposed,there)` in `we had to stay--my mother ... exposed` | `stay` infinitive of necessity, absolute exposed supplement with mother patient |
| N646 | `at` in `at once` becomes N, and `captain's` is interpreted as COPULA | Temporal PP and source genitive `dead captain's body` |
| N653 | `Will you be improved?` has no MODALITY link for `Will` | Interrogative modal scope and passive/stative patient `you` |
| N659 | `Oh` has type PERSON and `Master` is verb with `AFFECTED(Master,Copperfield)` | Interjection + honorific vocative `Master Copperfield`, not mastering Copperfield |
| N662 | `"A sweet lady, Master Copperfield!" said Uriah Heep` has only AGENT(said,Uriah) | Reported-content relation, nominal exclamation and vocative |
| N673 | `voice` in `in a low voice` is selected V, governing `REPORTED_CONTENT(voice,Be)` | Reporting predicate is `added`, with manner PP `in a low voice` |
| N674 | `read` in `the service was read` becomes N, `I` becomes N | Source passive verbal `read`, remembered location relative, and coordinated motion |
| N675 | `had` from `hadn't` is selected as V with `AGENT(said,had)` | Negative perfect auxiliary inversion and subject `I` of `said` |
| N680 | `I hope not` gives only AGENT(hope,I) and unlinked `not` | Negative proform / content of hope |
| N682 | `contrast` in `What a contrast between him and his friend!` is selected V | Nominal exclamation with `contrast` as noun |
| N687 | `I` in `that I suppose is...` is N; `ATTRIBUTE(suppose,I)` | Speaker parenthetical `I suppose` with overt subject |
| N688 | `it has been` selects `it` as POSS and `has` as N | Finite perfect of `be`, not a possessive NP |
| N692 | `does not follow` contains an unlinked negation | Negation scopes over `follow` in second quoted clause |
| N696 | Existent `There` selected N as AGENT of `is`; negative relative clause not scoped | Existential there + correct negated `can overcome` |
| N697 | `blue coat` contains `blue` N and `coat` V with `AGENT(coat,blue)` | Noun `coat` modified by adjective `blue`, object of `wore` |
| N701 | In `"Dear, dear Elizabeth!"`, first `Dear` is N/PERSON and graph has **zero edges** | Exclamative vocative and repeated address, not a person named Dear |
| N703 | `O blessed sleep!` has `O` PROPER-NOUN as `AGENT(blessed,O)` | Apostrophe/exclamation addressed to sleep, not an act by a person `O` |
| N707 | `You would not if you saw him`: `not` unlinked | Anaphoric negative modal consequent and subordinate if-condition |
| N720 | `a kind of panic` contains `panic` V with `AGENT(panic,kind of)` | `panic` noun as affective state experienced by `I` |
| N722 | `league` V, `rose` ADJ, and `AFFECTED(stood, Montanvert)` | Montanvert belongs to the main copular statement, `rose` is inverted finite verb with Mont Blanc subject |
| N725 | Negative `did not prepossess` has no negative-scope edge | `not` negates `prepossess`; `M.` is title, not topical bare noun |
| N740 | `Oh` is a PERSON node in intercalated dialogue | Overt exclamation/interjection, distinct from a person |
| N752 | `cannot` is N, `others` is V, `AGENT(answer,cannot)` | Negative ability auxiliary and `others` object of `for` |
| N755 | `I knew all now` gives `AFFECTED(knew,now)` | `all` is object/content, `now` is temporal modifier |
| N757 | `What are you talking about?` gives `ATTRIBUTE(are,you)` and `MODIFIER(you,talking)` | `talking` is the progressive verb of `you`, not a noun phrase modifier |
| N759 | `Oh` is PERSON and `will` is lexical V in `I really will` | Interjection + elliptical modal verb, with `you know` parenthetical |
| N760 | `it must have been` selects `it` POSS, `must` N, `have` N | Copular perfect modal chain, not an NP headed by must |
| N762 | `still` is lexical V, `read` N in `had ceased to read, still looking` | Temporal perfect with infinitive `read` and progressive participial adjunct |
| N770 | `Oh dear me` opens with `Oh` N and `me` N; source do-support is read V | Exclamation + yes/no question and reported speech, not nominal `Oh` |
| N772 | `Master` is V in the resumed source quotation | Vocative `Master Copperfield`, no verb `master` |
| N774 | Monetary `six pounds ten per annum` becomes a V `pounds` with `AFFECTED(pounds,annum)` | Numeric salary rate nominal, not a verbal event |
| N775 | `corner` in `in a corner` becomes V with an affected relative `where` | Locative PP and an actual existential `there used to be` |
| N777 | `Yes, almost every day` gives `APPOSITION(Yes,day)` | Affirmative minor speech act with temporal frequency, not noun apposition |
| N778 | `Is my father in town?` has only POSSESSOR(father,my) | Copular yes/no question with locative predicate |
| N782 | `could not be long a secret`: `not` is unlinked | Negative modal scope over `be ... a secret` |
| N788 | `herself` is selected DEGREE, `at present` contains `present` V | Reflexive object/complement and temporal `at present` PP |
| N792 | Quoted `“Oh! Mr. Collins!”` includes `Oh` PERSON; entire graph only has AGENT(began,Bennet), TOPIC(began,In) | Source speech content tied to `began the projected conversation`, not discarded |
| N793 | `had not mortified` has unlinked `not` and `had` V plus `mortified` ADJ | Negative past-perfect predicate in the if-clause |
| N798 | `discourage his coming here so very often` treats `so` as N object; `should not remind` loses negation | Possessive gerund subject, `so very often` degree adverb and negative modal scope |
| N800 | `offer to introduce` is selected with `offer` N, coordinated with `him` | Verb `offer` coordinated with `entreat`, infinitive `to introduce` as its complement |

## Separate review coverage from recognition coverage

The presence of a fully spanned parse, an automatically emitted graph and
a stable fingerprint does **not** establish that the selected attachment is
correct. The 200-case machine audit produces a concrete per-case dossier,
including **all 161 previously unreviewed** selected trees. Its automatic
flags can find some defects, but cannot assert any remaining review is
verified. It is intentional that the CI semantic acceptance gate **fails**
until the selected trees, roles and source analyses have independent
positive/negative and semantic controls.

The 500-case historical source signatures and the frozen 600/700/800
cohorts must not be edited to make these issues disappear. Corrections
belong in grammar/lexicon, with new selected tree+graph digests explicitly
reviewed and any earlier semantic repairs revalidated.
