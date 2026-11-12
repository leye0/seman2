"""Same-source fragment research for recurrent failures after 422/500.

Read source text from the pinned extractor. This only diagnoses component
availability and does NOT award grammatical completion to any passage.
"""
from scripts import probe_batch_418_roots as probe

probe.PROBES = {
    41: (
        ("Ain’t I what?", "CLAUSE"),
        ("Ain't I what?", "CLAUSE"),
        ("what", "NP"),
        ("what", "WH-NOM"),
        ("said the gentleman behind", "SPEECH-TAG"),
        ("the gentleman behind", "NP"),
        ("the gentleman", "NP"),
        ("behind", "ADV"),
        ("‘Ain’t I what?’ said the gentleman behind.", "CLAUSE"),
    ),
    56: (
        ("Without a story", "PP"),
        ("really", "ADV"),
        ("inquired Dora", "SPEECH-TAG"),
        ("creeping closer to me", "VP"),
        ("‘Without a story--really?’ inquired Dora, creeping closer to me.", "CLAUSE"),
    ),
    175: (
        ("listened", "VP"),
        ("wondered", "VP"),
        ("doubted", "VP"),
        ("was impatient for more", "VP"),
        ("listened, wondered, doubted, and was impatient for more", "VP"),
        ("Elizabeth listened, wondered, doubted, and was impatient for more.", "CLAUSE"),
    ),
    291: (
        ("a meeting", "NP"),
        ("which he anticipated with such joy", "REL-CLAUSE"),
        ("anticipated with such joy", "VP-GAP"),
        ("so strangely turned to bitterness", "VP"),
        ("A meeting, which he anticipated with such joy, so strangely turned to bitterness.", "CLAUSE"),
    ),
    294: (
        ("a creature", "NP"),
        ("capable", "ADJ"),
        ("capable of scaling the overhanging sides of Mont Saleve", "ADJP"),
        ("of scaling the overhanging sides of Mont Saleve", "PP"),
        ("a creature capable of scaling the overhanging sides of Mont Saleve", "NP"),
        ("Who could arrest a creature capable of scaling the overhanging sides of Mont Saleve?", "CLAUSE"),
    ),
    315: (
        ("by birth", "PP"),
        ("a Genevese", "NP"),
        ("am by birth a Genevese", "VP"),
        ("I am by birth a Genevese", "CLAUSE"),
        ("my family is one of the most distinguished of that republic", "CLAUSE"),
        ("I am by birth a Genevese, and my family is one of the most distinguished of that republic.", "CLAUSE"),
    ),
    384: (
        ("You", "NP"),
        ("'ll", "MODAL"),
        ("find", "V"),
        ("I do my duty", "CLAUSE"),
        ("You'll find I do my duty", "CLAUSE"),
        ("You'll find I do my duty.", "CLAUSE"),
        ("\"You'll find I do my duty.\"", "CLAUSE"),
    ),
    463: (
        ("He", "NP"),
        ("himself", "EMPHATIC-REFLEXIVE"),
        ("I thought", "CLAUSE"),
        ("looked somewhat paler and more stern than I was used to", "VP"),
        ("He himself looked somewhat paler", "CLAUSE"),
    ),
}
if __name__ == "__main__":
    probe.run()
