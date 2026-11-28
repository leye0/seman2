# Gap discovery campaign v1 (2,000 source units)

This is a research harness, not a new production parser.

| Cohort | Count | Reference |
| --- | ---: | --- |
| Frozen Novel-1000 v3 | 1000 | Existing exact native artifact, checked against pinned source |
| Contemporary | 400 | UP1 English-EWT test |
| Complex | 250 | UP1 English-EWT test, sampled using gold clausal edges or multiple verbal predicates |
| WSD | 200 | ALLamended, one annotated target per sentence |
| New literary dialogue | 150 | Same four pinned clean editions, non-overlapping source spans |

External UP1 selection excludes the 200 sentences used for model comparison.
Sampling is deterministic by hash, with source revision and full manifest
hash recorded; gold is used only to stratify or evaluate, not to change
predictions. New dialogue spans do not overlap the prior 1000; same editions,
not a held-out author test. ALLamended uses publisher XML token representation
(single space between elements) rather than pretending it is original prose.
UP retains original text and separately represents tokenized SRL inference.
ALLamended is CC BY-NC 4.0; UP1 inherits source terms; data stays in research
artifacts, not bundled with the application.

Source: https://github.com/SapienzaNLP/wsd-hard-benchmark/tree/74ff055519b3c426330df9974a6603a0e638a3db
Maru et al., ACL 2022, *Nibbling at the Hard Core of Word Sense Disambiguation*.
UP source and projection details are in SRL_REVIEW.md.

The workflow reuses 1000 native ERG results and runs the pinned native engine
on 1000 new source units. HanLP large observes all 2000, while the expensive
legacy AllenNLP comparator is limited to the 650 new gold SRL cases. Lexical
coverage (spaCy, WordNet, VerbAtlas) is checked on all 2000; GlossBERT only
runs on 200 gold WSD targets, with supplied lemma and POS. This avoids
thousands of unnecessary neural WSD calls and does not make AllenNLP a
production dependency. Native predictions, source spans, and gold targets
remain visible. Report includes paired gold hits, misses and recoveries,
per-role census, inventory gaps and native ambiguity/coverage signals.

No gold SRL on literary sentences: don't call absent frames errors without
annotation. Head-containment recall is not precision or full span F1;
paired oracle union is not a deployed system. WSD gold keys are compared to
all lemma keys of predicted synsets. Overlap with model training is unknown.
No rules, lexical overrides, rewrites, candidate filtering, or automatic
augmentation of the sources. For each future candidate require measured
new correct results and false positives on held-out data, deployed model
size, CPU latency, memory and license/maintenance review.

Artifacts from the original native run are retained 30 days; replay after
expiry requires reproducing that native benchmark and updating explicit
baseline provenance. The workflow records per-provider initialization,
inference wall time, process peak RSS, and research artifact size (not
application install size).
