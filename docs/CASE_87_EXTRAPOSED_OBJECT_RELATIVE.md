# Novel-500 #87 — evaluated action and supplementary object relative

> We judged it expedient, now, to tell her all we knew; which I recounted at length.

Baseline `f796cbaa0692925b09e29bcf74b9873c51ede84f` (488/500). David
Copperfield case `766:1d4f2bfad396bcbd`, normalized paragraph 5500, first
source unit at offsets 0–82. The existing source graph already keeps the
semicolon inside the utterance and identifies the supplementary relative.
The baseline has roots without a valid analysis. Removing the commas or
parsing pieces independently revealed a misleading possessive analysis for
`it expedient` and a single object for `her all we knew`.

The selected tree keeps anticipatory object `it`, adjective `expedient`,
both commas of the temporal supplement and the extraposed evaluated
action. `We` judges and is the understood agent of telling. The two overt
arguments of `tell` have separate roles: recipient `her` and theme
`all we knew`. The zero relative `we knew` restricts `all` and has its
own object gap. The supplementary relative preserves its own subject
`I`; `which` fills the object gap of `recounted` and reprises the theme
of telling, not the act of judging or the recipient. `At length` modifies
the recounting and `now` does not modify `knew`.

The existing public parser proves the source subject and manner spans.
The bounded assembly requires a complex-transitive evaluative frame,
an adjective licensed in it, a ditransitive content verb, and agreeing
finite knowledge and report predicates with transitive readings. It
uses source punctuation and lexical candidates without adding a global
grammar route or stripping alternatives from the public lattice. The
content-reprise link is limited to this overt lexical construction,
not a rule that all semicolon relatives attach to the closest NP.

Tests verify the source ranges, the two object gaps, semantic links
and prohibited attachments, an unrelated plural example and eleven
near-miss controls. The fixed cohort, WordNet 3.0, public corpus gateway
and search limits are unchanged.
