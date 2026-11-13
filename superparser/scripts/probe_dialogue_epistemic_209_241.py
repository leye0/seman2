"""Source-grounded constituent probes for Austen #209 and #241.
Success on a fragment is diagnostic only; never promoted without a whole
exact-source selected-tree proof under the pinned 50k/500k/10s budget.
"""
from scripts import probe_batch_418_roots as probe

probe.PROBES = {
    209: (
        ("Colonel Forster came himself", "CLAUSE"),
        ("Colonel Forster", "NP"),
        ("came himself", "VP"),
        ("till Colonel Forster came himself", "CLAUSE"),
        ("not one of you", "NP"),
        ("one of you", "NP"),
        ("a doubt", "NP"),
        ("not one of you entertained a doubt", "CLAUSE"),
        ("I suppose", "CLAUSE"),
        ("of their being really married", "PP"),
        ("their being really married", "NP"),
        ("being really married", "VP"),
        ("really married", "ADJP"),
        ("of you", "PP"),
    ),
    241: (
        ("they all removed to Brighton", "CLAUSE"),
        ("they all", "NP"),
        ("removed to Brighton", "VP"),
        ("to Brighton", "PP"),
        ("When they all removed to Brighton", "CLAUSE"),
        ("you had no reason", "CLAUSE"),
        ("no reason", "NP"),
        ("I suppose", "CLAUSE"),
        ("to believe them fond of each other", "VP-NP"),
        ("believe them fond of each other", "VP"),
        ("them", "NP"),
        ("fond of each other", "ADJP"),
        ("of each other", "PP"),
        ("each other", "NP"),
        ("fond", "ADJ"),
    ),
}
if __name__ == "__main__":
    probe.run()
