# Novel-500 #363 and #480 — embedded relatives

Base `e03c3261e1a445e74e8b016888c3feb05ff78bda`, cohort
`d3283e7769d1ab73ea04279fc448aca9c64ec2213afb6164c90aa1c5de78380f`, WordNet 3.0.
The corpus gateway, segmentation, 50,000 forest items, 500,000 k-best
work units and 10-second deadline are unchanged. The two intact source
units previously had roots without a valid analysis.

## #363 — Frankenstein

> Sometimes I sat with my eyes fixed on the ground, fearing to raise them lest they should encounter the object which I so much dreaded to behold.

The original lattice had no conjunction reading of *lest*. A scoped
reading attaches the preventive clause to *raise*. The *with* absolute
has plural *my eyes* as the passive subject and *on the ground* as the
location of *fixed*. Matrix *I* controls *fearing* and *raise*. The
relative's own *I* controls *behold*. *So much* modifies *dreaded*,
which selects the infinitive. The nominal fills the direct object of
*behold* and the whole relative-bearing NP is the object of *encounter*.

The independent positive substitutes *her hands folded on the table*
and *the instrument … to handle*. Contrast cases include an overt
infinitive object, an intransitive infinitive and loss of subject control.

## #480 — Treasure Island

> The squire was sitting down, as white as a sheet, thinking of the harm he had led us to, the good soul!

The isolated matrix ranked *sitting* as an adjective. The selected
composition proves the progressive auxiliary and particle *down*.
The equative depicts the squire and *thinking* shares the subject.
*Of* selects the whole relative-bearing NP. *He* is the subject of
*had led*, *us* is its direct object and *the harm* fills the stranded
directional *to*. *The good soul* is an apposition to the matrix subject.

The independent positive substitutes *the captain … kneeling down* and
*the place she had brought us to*. Contrasts fill the gap overtly,
remove its licensed directional frame, break agreement or omit the
apposition comma.

## Validation

The targeted tests assert selected source spans, exact semantic edges
and forbidden misattachments. The scoped patterns do not cover every
preventive clause or stranded preposition. No new cross-clause
pronoun coreference is inferred.

[PR #66](https://github.com/leye0/seman2/pull/66) advanced Novel-500 from
468 to 470. The official unresolved queues differ only by these two cases.
All 468 prior selected trees matched locally, 30/30 historical dialogues
remain complete, and 762 tests passed. See [the cohort record](CURRENT_COHORT.json).
