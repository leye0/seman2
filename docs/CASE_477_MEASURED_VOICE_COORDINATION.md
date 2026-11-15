# Novel-500 #477 — measured passive and active coordination

Base: `2cb050659450cc7f3363767d361ffe7cb8dd17bd`.
Source case: `120:1a8e1aa200463f0d` (paragraph 448, unchanged).

> The HISPANIOLA was laid a couple of points nearer the wind and now sailed a course that would just clear the island on the east.

The preceding utterance ends after Captain Smollett issues orders. The target
preserves the full source sentence through the period and needs no segmentation
change. The base has roots but no valid selected tree. It parses `was laid`
alone, but not the measured passive. If both the measurement and the relative
are removed, its rank-one tree instead makes the noun reading of `now` the
subject of an independent second clause.

The selected composition keeps one proper-name subject and two agreeing finite
predicates. The ship is the theme of passive `laid` and agent of active
`sailed`. In the first conjunct, `a couple of points` measures `nearer`,
whose landmark is `the wind`. In the second, `now` modifies `sailed`.
The relative stays inside the object `a course`: the course is the subject of
`clear`, and `would`, degree `just` and the directional `on the east`
stay with `clear`. `The island` is its direct object, not the host of the PP.

The scoped composition uses the shared-subject assembler, real finite and
participial forms, lexical transitivity, an overt unit and a spatial comparative,
a separately licensed subject relative, and exact source offsets. An independent
plural example uses a cardinal measure and `closer to`. Near misses cover
agreement, missing or invalid participles, singular units, wrong prepositions,
independent subjects, object relatives, and a non-base verb after the modal.

Validation uses the unchanged Novel-500 cohort, public corpus entry point,
WordNet 3.0 and 50k forest / 500k enumeration / 10s per-case budgets.
