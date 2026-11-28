# Lightweight semantic role resources

Opt-in local VerbAtlas 1.1.0 tables from the official SapienzaNLP NounAtlas
repository, and SemLink 2 mappings from its official GitHub repository.
Every file has a pinned repository revision, size and Git blob hash.
The installer verifies the exact upstream bytes; updating requires reviewing
a new manifest, not silently replacing the resource in an inference run.
No extra pip requirements, no model weights, no network during analysis.
The raw tables retain their publisher headers. VerbAtlas CC BY-NC-SA 4.0;
BabelNet mapping has its own BabelNet license; check redistribution and
commercial permissions separately. SemLink's linked resources have their
own terms. Do not redistribute data with the application by default.

```sh
PYTHONPATH=superparser python -m scripts.install_role_resources ./role-data
# Add --wsd --role-resources ./role-data to the existing parser CLI
```

Reuse one RoleResources object for repeated calls. Exact WordNet 3.0 offset
joins preserve every WSD verbal alternative and native frame/role record.
PropBank and VerbNet lookups require official identifiers; no inferred roleset
from lemma, synonym substitution, candidate filtering, or filling source
arguments from frame priors. The JSON contains the independent inventories
and original model predictions, not corrected MRS or SRL.

The audit reuses the frozen GlossBERT artifact (no model load) and measures
lookup time, initialization and Python allocation peak, mapped senses,
and total table bytes. It tests whether retort.v.01 has a published role
structure where PropBank return.xml lacks a speech sense. Inventory coverage
does not prove any actual source constituent fills those roles. Evaluate
a separate knowledge-conditioned model only if measurable gain justifies
its weight, latency and false-positive rate.
