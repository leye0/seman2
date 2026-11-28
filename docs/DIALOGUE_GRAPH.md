# Dialogue graph v1

Seman2 produces a source-linked graph over all native MRS alternatives, with
variable/handle names scoped to view and rank. Native EPs, arguments, HCONS and
ICONS are projected to exact unit-relative ranges. Whole-source and independent
component analyses are never overwritten.

A reporting event is a hypothesis grounded in the overt reporting cue's native
predicate. Its native ARG1 supplies a possible speaker only if an overt entity
anchor lies inside the reporting clause. Prefer whole-unit evidence when
available (isolated inverted tags often parse as imperatives). Multiple
different anchored alternatives remain ambiguous. First-person singular
deixis is a candidate link to a quotation's attribution, not variable equality;
embedded quotations are excluded. No automatic addressee or third-person
coreference.

For intercalated reporting tags, the original outer quote interiors are
exposed as an additional discontinuous input view. Every character (including
the separator) is copied from an exact source position. Both the original
quote-final comma and an explicitly recorded omission are tried; no punctuation
or words are invented, and the original source and MRS remain unchanged.
Native shared-variable and qeq links across distinct quote spans expose
cross-fragment dependencies without new grammar rules. The views remain
alternative readings, not one fabricated DELPH-IN MRS.

The audit replays the successful 327-dialogue/630-component artifact and
resolves the original pinned sources. It evaluates all 49 intercalated turns,
records exact view mappings, all native output and per-case links. Counts are
diagnostics, not semantic accuracy; manual speaker/dependency gold checks
remain required. No reported success can change whole-unit coverage.

Run: [dialogue graph workflow](../.github/workflows/erg-dialogue-graph.yml).
