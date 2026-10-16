# VerbNet → WordNet → Left-to-Right hints (experimental)

This module **does not** replace or modify the Seman2 runtime. It compiles
VerbNet 3.4 XML, optionally joins VerbNet *WordNet sense keys* to WordNet 3.0
`dict/index.sense`, and exposes ordered post-verbal grammatical expectations.
It does not create a parse forest or generate Python grammar rules.

## Build (once, offline)

~~~bash
cd superparser
python -m research.verbnet_lr /path/to/verbnet/verbnet3.4 \
  --wordnet-sense-index /path/to/WordNet-3.0/dict/index.sense \
  --output /tmp/verbnet_lr.json
~~~

Obtain the XML from https://github.com/cu-clear/verbnet. No XML is vendored.
If `--wordnet-sense-index` is absent, alignment is **lemma-only**, not verified.
Frames marked `unresolved` have VerbNet keys but no matching WordNet offsets;
they are not used as sense-verified hints.

## Read-only query

~~~python
from research.verbnet_lr import read_index
from research.verbnet_lr.adapter import predict_candidate

index = read_index('/tmp/verbnet_lr.json')
# LexicalCandidate is produced by Seman2's existing morphology/WordNet lattice.
hint = predict_candidate(index, candidate, ('NP', 'PREP:to'))
print(hint.status, hint.confidence, hint.next_events)
~~~

`observed` is a stream of **completed category events** since the lexical verb,
not surface words. Example: *give John a book* → `NP, NP`; *give a book to John*
→ `NP, PREP:to, NP`. The caller owns event recognition, including morphology,
auxiliaries, co-reference, head selection and ambiguity. `PREFIX` is provisional;
`ATTESTED` means some VerbNet frame ends here, not that the sentence is valid.
`UNKNOWN` **never** means ungrammatical. `next_events` provides priorities, not
hard constraints. Sense-filtered predictions (`sense_verified`) may be more
trustworthy but are still not exhaustive.

## Current boundary and limitations

- An exact match requires WordNet's `index.sense`; Seman2's lexical sense IDs
  contain a synset offset, and the adapter joins without creating new candidates.
- VerbNet members in nested subclasses inherit **ancestor** frames; a parent
  member does not inherit its children's frames.
- XML syntax not understood by the prototype is **skipped and counted**, not
  silently reduced into a misleading pattern.
- Some VerbNet `SYNRESTRS` are projected to infinitive/gerund/clause categories;
  the remaining restrictions are *not* fully enforced. No negative syntax claims.
- An underspecified `<PREP>` is represented as `PREP:*`; it is weak evidence.
- `WordNet 3.0` vs VerbNet sense mappings may not cover every key. Track this
  alignment coverage before enabling the hints on any parser hot path.
- Prefix index is a shared trie per verb, built lazily. It is not a packed
  parse forest, and does no global search or backtracking.
- Requires controlled evaluation on the full VerbNet corpus and the Seman2
  positive/negative/holdout sets **before** any production integration.

## Fast tests

~~~bash
cd superparser
python -m unittest discover -s tests -p 'test_verbnet_lr.py' -v
~~~

## Next experiment

Measure coverage, index size, time per `predict_candidate()`, prefix memory,
mutant discrimination *without hard rejection*, and compare A=baseline,
B=lemma-only, C=exact WordNet-sense hints on held-out sentences. Then wire the
hint interface into the existing predictive Left-to-Right research engine,
not into `vector_chart.py`.
