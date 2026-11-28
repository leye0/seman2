# External knowledge providers (observation only)

ERG remains the only engine responsible for grammatical output. This optional
layer simply exposes independent existing resources. No new grammar, candidate
filter, synonym substitution, title rule, suffix rule, speaker rule or
disambiguation algorithm is introduced.

- WordNet: complete synset inventory for queried forms (not a WSD decision),
  definitions, lexical categories, synonyms, frames and hypernyms.
- VerbNet 3.3 via NLTK: class identifiers, roles, frames and original XML.
  The existing historical 3.4 compiled file is not modified or used for this
  independent comparison.
- FrameNet 1.7 via NLTK: lexical units, frame identifiers and frame elements.
  Lookup is not frame-semantic parsing.
- spaCy en_core_web_sm 3.8.0: native tokens, lemmas, POS, morphology, dependency
  predictions and named entity spans. They remain independent observations;
  spaCy does not replace ERG.
- English Wiktionary: optional explicit lookup through the official MediaWiki
  API, including original page revision and wikitext. No automatic sense parsing
  or full-dump installation yet. Network errors are distinguished from absent
  entries. No text paragraph is transmitted.

Install:
```sh
pip install -r requirements-knowledge.txt
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
python -m nltk.downloader wordnet verbnet3 framenet_v17
```

Python:
```python
from seman_parser.knowledge import Knowledge, Wiktionary
observations = Knowledge().inspect("Your paragraph.")
page = Wiktionary().lookup("return")  # explicit external request
```

CLI: add `--knowledge` to the existing ERG CLI; optionally
`--wiktionary-word return` (repeat for additional words). Without those flags
there is no behavioral change, added dependency, or network access.

The workflow inventories all 327 frozen dialogues, with per-source token and
entity offsets. Specific lexical probes are evaluation examples only. Merely
finding a sense or NER span does not demonstrate better ERG accuracy; a future
experiment should use an existing contextual WSD/frame/SRL model and compare
gold annotations without modifying the original grammar.
