# SRL review: preserve the original benchmark, diagnose before replacing

Original run 46148103498: 49/68 exact targets, 57/68 predicate-found
targets. All 30 source passages aligned exactly. Inspection of the actual
artifact 15264054026 found five completely empty native SRL outputs:
SRL-009, 011, 017, 026, 029. SRL-012 has a different predicate (smiled),
not repaired. This is not an offset scoring bug. Missing predicates and
missing arguments are separate failure classes.

## Source review

HanLP official English ModernBERT checkpoint docs:
https://hanlp.hankcs.com/docs/api/hanlp/pretrained/mtl.html
The published F1 (95.86 large, 92.57 base) is not our partial-target recall.
Source `hanlp/components/mtl/multi_task_learning.py` at upstream
6962907e37dfa467fa6dee164b5b1d0a904b24db supports raw string, batch,
and tokenized input, plus task selection. Review tests these modes separately;
no automatic choice of the highest-scoring variant. Span ranking has
candidate pruning and maximum argument width in upstream configuration.
No tuning of these parameters in this experiment.

## Annotation audit

Reviewed official PropBank v3.4 frame XML at
https://github.com/propbank/propbank-frames/tree/c66e0ccf28b53f00051b187db83e937b5bee2e32/frames
rather than generalizing ARG0 as subject.

- 001/002 give.01, 003 send.01: giver/sender 0, thing 1, recipient 2.
- 004/006/011/013/014/030 open.01: opener 0, thing opening 1;
  011 close.01: closed thing 1. Adjunct labels remain manually annotated.
- 005/010/012 repair.01: repairer 0, object 1.
- 007 read.01: reader 0, thing read 1. 008 cut.01: cutter 0, thing cut 1.
  Instrument is not in the original score (official cut.01 role 3).
- 009 break.01: breaker 0, thing broken 1, matching official example
  with waves as ARG0. No grounds to remove the case.
- 010 promise.01: promiser 0 (recipient 1, promised action 2).
  Original test only annotated 0 plus repair object.
- 015 tell.01: speaker 0, utterance 1, hearer 2.
- 016/018/027 say.01: sayer 0, utterance 1.
- 019 exclaim.01, 020 murmur.01, 023/024 shout.01: speaker 0, utterance 1.
- 022 ask.01: asker 0, question 1, hearer 2.
- 025 return.02: giver 0, thing given 1; 026 return.01: entity in motion 1.
- 027 believe.01: believer 0, belief 1.
- 028 leave.11: departure; causal adjunct remains manually annotated.
- 029 wash.01: washer 0, thing washed 1.
- 030 cool.01: thing cooling 1.
- 017/021: literary 'return' = answer back. Official return.xml has no
  corresponding speech roleset. Keep original targets as semantic probes;
  additionally report PB-compatible denominator excluding these two cases.
  This does not invalidate WordNet's documented reply sense.
- NEG, TMP, MNR, LOC, CAU, MOD boundaries and labels are plausible manual
  annotations but have not been independently adjudicated. Passive by-phrase
  and quotation conventions must be distinguished from syntax.

All original labels are preserved. No claim of fully human-adjudicated gold.
No post-hoc correction of predictions or cherry-picked score.

## External test

UniversalPropositions/UP-1.0 English EWT test file pinned to
b955f2aa8295834fcd0256c131de641116a8443a. The English data were derived
from PropBank human annotations, projected from constituent spans onto UD
heads; unlike most UP1 languages this is not purely machine-predicted SRL.
See https://github.com/UniversalPropositions/UP-1.0/blob/b955f2aa8295834fcd0256c131de641116a8443a/UP_English-EWT/README.org
Select 200 deterministic eligible sentences, verbal predicates only,
5–35 tokens, no malformed/missing rows, source tokenization supplied.
Compare predicted labelled spans containing annotated heads. This is
restricted recall, not span precision or F1. Training overlap with the
published checkpoints is unknown. A full OntoNotes/CoNLL test requires
licensed material; don't imply this experiment reproduces published F1.

Two HanLP checkpoints test model sensitivity without production changes.
Independent architecture candidate AllenNLP SRL-BERT (official
`structured-prediction-srl-bert.2020.12.15.tar.gz`), documented predictor
https://docs.allennlp.org/models/v2.10.1/models/structured_prediction/predictors/srl/
uses a legacy runtime and a different predicate detection strategy. Evaluate
in isolation if both HanLP models show failures; no replacement yet.

The independent SRL-BERT run now executes in its own Python 3.9 environment, using the upstream predictor and identical external sample. Its official model card reports 86.49 OntoNotes test F1, with a different task setup from HanLP. The native predictor selects VERB/AUX tokens using spaCy; no new Seman2 predicate heuristics. HanLP pretokenized calls explicitly set `skip_tasks='tok*'` per https://hanlp.hankcs.com/docs/data_format.html.

## Measured outcome: run 46149251926

Both ModernBERT models completed all five modes and the paired external sample.
The exact target counts are invariant across inference modes: large 49/68,
base 43/68. All 30 inputs have exact source alignment. Empty raw-input frame
counts: large 5, base 7. Pretokenized input changes some frames but not exact
recall. The failures are reproducible, not explained by batching or the scorer.

External UP-EWT: 1,053 target relations on 200 passages, 1,088 eligible.
Source SHA256 f511b4b39cf9525945fbb89660757b401d339d2deee805a36c3b4fc9ea2cd8b7.
Large: 1,037 predicate-found, 890 labeled head hits. Base: 1,023 and 852.
Pairwise native results (artifacts 15265745700 and 15265192031):

| Sample | Both | Base only | Large only | Neither | Oracle union |
| --- | ---: | ---: | ---: | ---: | ---: |
| Diagnostic | 36 | 7 | 13 | 12 | 56/68 |
| External | 812 | 40 | 78 | 123 | 930/1053 |

Base independently recovers both roles of 'broke' in 'The wind broke the
window', plus 'closed', 'repaired' and intransitive 'returned' targets
missed by large. This shows complementarity; union is an oracle availability
bound, not an actual ensemble accuracy or precision. No automatic selection
or merged production analyses. The paired analysis is reproducible via
`python -m scripts.compare_srl_overlap --base BASE_DIR --large LARGE_DIR --out overlap.json`.

Independent AllenNLP initial run 46149251909 failed before inference because
Ubuntu 26.04 does not provide Python 3.9 in setup-python. Comparator moved to
Ubuntu 22.04, pinned Python 3.9.25 and the spaCy 3.3.0 model; still experimental.
