# Corpus and data preservation policy

The clean-up must **not delete or rewrite the novels, Wikipedia/wiki data, linguistic resources, or user-generated corpus evidence**.

## Confirmed tracked cleaned novels

- `superparser/research/verbnet_lr/corpora/david_copperfield_766.txt`
- `superparser/research/verbnet_lr/corpora/pride_and_prejudice_1342.txt`
- `superparser/research/verbnet_lr/corpora/frankenstein_84.txt`
- `superparser/research/verbnet_lr/corpora/treasure_island_120.txt`
- `superparser/research/verbnet_lr/corpora/manifest.json`, corpus README and preprocessing scripts.

Keep the textual contents and original quote/punctuation evidence unchanged; use manifest checksums and clean-source reproducibility when updating data. Also retain historical `data/` inputs and any unrelated `corpus`, `wiki`, `Wikipedia`, `Wikidata`, `*.txt`, `*.jsonl` or linguistic assets.

## Wikipedia corpus status

At this cleanup starting point, the Git tree of `main` did **not show an obviously named tracked Wikipedia dataset**. This is an inventory limitation, not evidence that the user’s Wikipedia corpus does not exist: it may be external, locally generated, archived under another name, or held in a connected storage/service. The cleanup deliberately **does not touch any data directory** and must identify the concrete Wikipedia corpus storage before future data consolidation. Do not claim to have migrated or preserved unseen external files.

## Safe cleanup rule

Only remove **legacy executable implementations, their obsolete tests and no-longer-needed CI triggers** after checking their runtime dependents. Historical prose, run links, data and corpus scripts needed for loading/cleaning remain. Git history is the reversible archive for explicitly deleted source paths. Never delete a corpus just because a benchmark is outdated.
