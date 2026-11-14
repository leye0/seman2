# Novel-500 #73, #95 and #348 — finite temporal scope

Base `f373d12fb32660feeb55341b2c6f193647d3368f`, unchanged cohort
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`.
WordNet 3.0, canonical `parse_corpus_case`, 50,000 forest items,
500,000 k-best work units, 10-second deadline. The source paragraphs and
both segmentation views preserve one complete utterance per case.

## #73 — a temporal adjunct between a verb and its content

> I thought, as they came towards us, that they were well matched even in that particular.

Previously a timeout. The selected analysis places the simultaneous
*as*-clause on *thought*, not on *matched*. *That* introduces the
proposition selected by *thought*. *They* is the theme of the passive
predicate *matched*, with *well* and *even in that particular* internal
to that proposition. No change to the original commas.

## #95 — a fronted adjunct after a connective

> Accordingly, when Mr. Peggotty came home about nine o’clock, this unfortunate Mrs. Gummidge was knitting in her corner, in a very wretched and miserable condition.

Previously forest saturation. Isolated pieces admitted analyses that
split the title at its period, misread *o’clock* as part of a gerund, or
interpreted *knitting* as nominal. The selected tree verifies the titles
and abbreviation periods, the destination *home* and the clock PP as
separate dependents of the arrival. *When* dates the progressive *was
knitting*. *In her corner* locates the action. The comma-delimited
coordinated state describes Mrs. Gummidge rather than the arrival,
the location, or Mr. Peggotty.

## #348 — a fronted adjunct without a closing comma

> When I mingled with other families I distinctly discerned how peculiarly fortunate my lot was, and gratitude assisted the development of filial love.

Previously roots without a valid analysis. The first comma follows the
entire first conjunct and is not the temporal boundary. Source preanalysis
now proposes the earlier boundary before the second *I*. The adjunct
scopes over *discerned*, not the embedded *was* or the independent
second conjunct *gratitude assisted …*. *How peculiarly fortunate*
is the degree predicate of *my lot*. *Of filial love* belongs to
*development*, not to *assisted*.

## Tests and scope

The shared finite temporal interface carries the overt subordinate
event into three separate host constructions. Positive controls vary
subjects, predicates, clock time, titles and nominal complements.
Counterexamples test malformed punctuation, agreement, unlicensed
movement/valency and the absence of a genuine adjective. The tests
assert exact source spans, selected rank-one children and negative
semantic links. No general ambiguity resolution is claimed for
unpunctuated fronted temporal clauses.

See [PR #68](https://github.com/leye0/seman2/pull/68) and
[the cohort record](CURRENT_COHORT.json) for the official comparisons.

The official cohort advances from 472 to 475. All 472 prior selected
trees match locally. All 30 historical dialogues and 769 unit tests pass.
Case #110 remains unresolved. The workflow stopped at the wall-clock
cutoff, but isolated replays reach the same k-best cap of 500,001 units
in both versions without activating the new composition.
