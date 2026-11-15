# Novel-500 #124 — a condition scopes over three consequences

> If that were so, my sacrifice was nothing; my plainest obligation to her unfulfilled; and every poor action I had shrunk from, I was hourly doing.

Case `766:e5f30c6dd18d4da6` is the complete 146-character utterance at
offsets 294–440 of normalized David Copperfield paragraph 6913. The preceding
sentence presents the narrator's uncertainty about Agnes. `If that were so`
makes the three following consequences hypothetical, rather than asserting
the last two separately. Both semicolons and the overt `and` remain.

The canonical pass failed. In local pieces it interpreted `were` as
plural, and the fronted nominal produced a spurious nested relative.
The selected grammar licenses irrealis `were` only under the scoped
conditional, keeps the overt copula in the first consequent and represents
the second as copular ellipsis rather than inserting another verb.
`To her` stays with `obligation`.

In the third consequent, `every poor action` is the antecedent of the
relative and fills the missing object of its own stranded `from`. The
full fronted nominal then fills the different object slot of progressive
`doing`. `Hourly` modifies `doing`, not `shrunk`. The ordinary source
parser supplies the component nominals, and all remaining word candidates
and punctuation are source-backed. An independent positive and ten
near misses exercise the exact selected-tree and scope checks.
