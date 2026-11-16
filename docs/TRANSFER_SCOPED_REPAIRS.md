# Transfer-24 — scoped repairs after the first diagnostic

This is a replay of the same 24 source units examined in [PR #91](https://github.com/leye0/seman2/pull/91), not a new unseen measure. The comparison baseline includes the independent statement/wh-question sequence in [PR #92](https://github.com/leye0/seman2/pull/92). No unrestricted grammar rule, book text, or token budget is changed.

## Selected-tree changes

| Source case | Rank-one attachment or relation repaired |
|---|---|
| T35-0509 | `Really and truly` is one coordinated adverb phrase on the auxiliary ellipsis. There is no invented predicate after `I do`. |
| T35-0085 | `with his finger` is the instrument of `pointed`, not a modifier of `the part`. The scoped plan requires an overt pointing frame and the subject's own body-part phrase. |
| T35-0200 | `but a pair …` is an exception to the negative domain `nothing`. It is not coordinated with `them` inside the locative PP. |
| T35-0050 | The overt modal scopes over both `travel` and `verify`. The full nested nominal belongs to `verify`; the exemplifier remains a discourse supplement. |
| T35-0485 | The previously incomplete case has two independently verified finite conjuncts. The PP between commas attaches to `returned` only. `Took up` retains its particle and `the lamp` its direct-object role. |
| T45-0675 | The contracted negation attaches to the inverted modal. `you` is an unmodified subject and `have sent …` remains a perfect predicate. |
| T45-2707 | The quoted cheer is an interjection, not a proper name. `Moody Spurgeon` is one speaker constituent, not a speaker plus an addressee. |
| T45-0573 | The command has its own comparison and is followed by a separate verbless closing. Both literal stops and quote delimiters survive. |
| T45-2808 | `Wednesday` locates the progressive event `be haunting`, not `the post office`. The adjacent inverted tag identifies the source speaker. |
| T45-2891 | `do` supports negation of the cognition clause. The first comparison is its complement. The assertion after the dash is coordinated with the whole negative cognition clause, not nested in its complement. |

The source-backed assembler submits all fragment proofs to the same parser and divides the existing item and k-best ceilings among the fragments and assembly. Failed or saturated proofs fall through to the normal parse. Controls distinguish a clausal supplement from a PP, separate source acts from a nominal fragment, distinguish a real reporter from adjoining narration, exercise productive variants, and inspect source spans and semantic links rather than mere recognition.

## Validation and remaining scope

The ordered source identity stayed `e628012351233ce6605b77257d048be7bfee05aa7f398286162365c96a3b8b8b`. The runner reports the separate digest of derived preanalysis because the coordination and attribution annotations are now more informative. Its identity gate still rejects changes to wording, offsets, punctuation, membership or order.

The pinned Novel-500 retains 500/500 including the 30 historical dialogues. The ordered rank-one tree, source identity, status and saturation snapshots match byte for byte (SHA-256 `5a0a5b189ba1fb0f65e1da26eee423b2fe5b818ba8b57e91d98f7fcfee149a07`), with 16 pre-existing forest flags and no k-best flag. The replay completed 24/24, up from 23/24. The only previously saturated forest is still T35-0071. No timeouts or k-best exhaustions were introduced. The ten rank-one changes above are not an estimate of accuracy on unseen sentences. The remaining diagnostics include reduced-clause control, participial coordination and finer nominal/relative attachments. The two-line quoted verse remains separate from the prose-tree judgment.
