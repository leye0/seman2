"""Systematic exception mining: find where the parser breaks.

Instead of fixing one construction at a time, this module sweeps
families of English exceptions — irregular morphology, exceptional
syntax, boundary cases — and reports what fails. Each family is a
linguistic class, not a word list.

Usage:
    python -m seman_parser.exceptions_report
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Case:
    text: str
    family: str
    note: str = ""


@dataclass
class FamilyResult:
    family: str
    total: int = 0
    passed: int = 0
    failures: list[Case] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


# ---------------------------------------------------------------------------
# Exception families. Each entry is a linguistic class of English
# exceptions, not a corpus-specific list.
# ---------------------------------------------------------------------------

FAMILIES: tuple[tuple[str, tuple[Case, ...]], ...] = (
    (
        "irregular_verbs",
        (
            Case("He went home.", "irregular_verbs", "go/went/gone"),
            Case("She wrote a letter.", "irregular_verbs", "write/wrote/written"),
            Case("They ate the cake.", "irregular_verbs", "eat/ate/eaten"),
            Case("He took the book.", "irregular_verbs", "take/took/taken"),
            Case("She sang a song.", "irregular_verbs", "sing/sang/sung"),
            Case("He ran fast.", "irregular_verbs", "run/ran/run"),
            Case("She came early.", "irregular_verbs", "come/came/come"),
            Case("They saw the bird.", "irregular_verbs", "see/saw/seen"),
            Case("He bought milk.", "irregular_verbs", "buy/bought/bought"),
            Case("She brought food.", "irregular_verbs", "bring/brought/brought"),
            Case("He taught the class.", "irregular_verbs", "teach/taught/taught"),
            Case("She thought about it.", "irregular_verbs", "think/thought/thought"),
            Case("He caught the ball.", "irregular_verbs", "catch/caught/caught"),
            Case("She felt happy.", "irregular_verbs", "feel/felt/felt"),
            Case("They built a house.", "irregular_verbs", "build/built/built"),
            Case("He kept the secret.", "irregular_verbs", "keep/kept/kept"),
            Case("She left early.", "irregular_verbs", "leave/left/left"),
            Case("He lost his keys.", "irregular_verbs", "lose/lost/lost"),
            Case("She made a cake.", "irregular_verbs", "make/made/made"),
            Case("He paid the bill.", "irregular_verbs", "pay/paid/paid"),
        ),
    ),
    (
        "irregular_nouns",
        (
            Case("The children played.", "irregular_nouns", "child/children"),
            Case("The men left.", "irregular_nouns", "man/men"),
            Case("The women arrived.", "irregular_nouns", "woman/women"),
            Case("The feet hurt.", "irregular_nouns", "foot/feet"),
            Case("The teeth ached.", "irregular_nouns", "tooth/teeth"),
            Case("The mice ran.", "irregular_nouns", "mouse/mice"),
            Case("The geese flew.", "irregular_nouns", "goose/geese"),
            Case("The people agreed.", "irregular_nouns", "person/people"),
            Case("The knives were sharp.", "irregular_nouns", "knife/knives"),
            Case("The lives changed.", "irregular_nouns", "life/lives"),
            Case("The wolves howled.", "irregular_nouns", "wolf/wolves"),
            Case("The shelves broke.", "irregular_nouns", "shelf/shelves"),
            Case("The oxen worked.", "irregular_nouns", "ox/oxen"),
            Case("The data arrived.", "irregular_nouns", "datum/data"),
            Case("The analyses were long.", "irregular_nouns", "analysis/analyses"),
        ),
    ),
    (
        "irregular_adjectives",
        (
            Case("She is better today.", "irregular_adjectives", "good/better/best"),
            Case("He is worse now.", "irregular_adjectives", "bad/worse/worst"),
            Case("It is farther away.", "irregular_adjectives", "far/farther/farthest"),
            Case("She is older than me.", "irregular_adjectives", "old/older/oldest"),
            Case("He is more careful.", "irregular_adjectives", "careful/more careful"),
            Case("This is the best one.", "irregular_adjectives", "superlative"),
        ),
    ),
    (
        "tricky_morphology",
        (
            Case("He was running.", "tricky_morphology", "double consonant"),
            Case("She was sitting.", "tricky_morphology", "sit/sitting"),
            Case("They were beginning.", "tricky_morphology", "begin/beginning"),
            Case("He was putting it away.", "tricky_morphology", "put/putting"),
            Case("She was getting ready.", "tricky_morphology", "get/getting"),
            Case("It was happening.", "tricky_morphology", "happen/happening"),
            Case("He was opening it.", "tricky_morphology", "open/opening (no doubling)"),
            Case("She was eating.", "tricky_morphology", "eat/eating (drop e)"),
            Case("He was lying.", "tricky_morphology", "lie/lying"),
            Case("She was dying.", "tricky_morphology", "die/dying"),
            Case("They were flying.", "tricky_morphology", "fly/flying"),
            Case("He was carrying it.", "tricky_morphology", "carry/carrying (y->i)"),
            Case("She was studying.", "tricky_morphology", "study/studying"),
        ),
    ),
    (
        "contractions",
        (
            Case("He doesn't know.", "contractions", "doesn't = does + not"),
            Case("She won't go.", "contractions", "won't = will + not"),
            Case("They can't see.", "contractions", "can't = can + not"),
            Case("It isn't ready.", "contractions", "isn't = is + not"),
            Case("He didn't leave.", "contractions", "didn't = did + not"),
            Case("She wasn't there.", "contractions", "wasn't = was + not"),
            Case("They haven't arrived.", "contractions", "haven't = have + not"),
            Case("We couldn't find it.", "contractions", "couldn't = could + not"),
            Case("I'm here.", "contractions", "I'm = I + am"),
            Case("She's ready.", "contractions", "She's = she + is"),
            Case("He's gone.", "contractions", "He's = he + has"),
            Case("They're waiting.", "contractions", "They're = they + are"),
            Case("We've finished.", "contractions", "We've = we + have"),
            Case("You'll see.", "contractions", "You'll = you + will"),
            Case("John's car is red.", "contractions", "'s possessif"),
        ),
    ),
    (
        "exceptional_syntax",
        (
            Case("There is a problem.", "exceptional_syntax", "expletive there"),
            Case("It is raining.", "exceptional_syntax", "expletive it"),
            Case("It seems that he left.", "exceptional_syntax", "extraposition"),
            Case("What he said surprised me.", "exceptional_syntax", "subject clause"),
            Case("He gave up.", "exceptional_syntax", "phrasal verb"),
            Case("She looked up the word.", "exceptional_syntax", "phrasal verb + NP"),
            Case("He turned the light off.", "exceptional_syntax", "phrasal verb separated"),
            Case("They made him leave.", "exceptional_syntax", "object control bare"),
            Case("She saw him leave.", "exceptional_syntax", "perception verb + bare"),
            Case("I want him to go.", "exceptional_syntax", "object control to"),
            Case("He is easy to please.", "exceptional_syntax", "tough movement"),
            Case("It was John who left.", "exceptional_syntax", "cleft"),
            Case("John, my brother, left.", "exceptional_syntax", "apposition"),
            Case("The more you learn, the more you know.", "exceptional_syntax", "correlative comparative"),
            Case("Not only did he leave, but he took everything.", "exceptional_syntax", "inversion + correlative"),
        ),
    ),
    (
        "exceptional_agreement",
        (
            Case("The team is winning.", "exceptional_agreement", "collective sg"),
            Case("The team are arguing.", "exceptional_agreement", "collective pl (BrE)"),
            Case("Everyone is here.", "exceptional_agreement", "everyone + sg"),
            Case("Each of the boys has a book.", "exceptional_agreement", "each + sg"),
            Case("The news is good.", "exceptional_agreement", "news uncountable"),
            Case("Mathematics is hard.", "exceptional_agreement", "-ics sg"),
            Case("The police are here.", "exceptional_agreement", "police pl"),
            Case("Bread is cheap.", "exceptional_agreement", "mass noun"),
            Case("Five dollars is enough.", "exceptional_agreement", "measure sg"),
            Case("A number of people were there.", "exceptional_agreement", "a number of + pl"),
        ),
    ),
    (
        "exceptional_word_order",
        (
            Case("What did he say?", "exceptional_word_order", "wh fronting"),
            Case("Never have I seen such a thing.", "exceptional_word_order", "negative inversion"),
            Case("Here comes the bus.", "exceptional_word_order", "locative inversion"),
            Case("Only then did he understand.", "exceptional_word_order", "only + inversion"),
            Case("So do I.", "exceptional_word_order", "so + inversion"),
            Case("Neither do I.", "exceptional_word_order", "neither + inversion"),
            Case("Hardly had he arrived when it started.", "exceptional_word_order", "hardly + inversion"),
        ),
    ),
    (
        "passive_exceptions",
        (
            Case("The box was opened by John.", "passive_exceptions", "passive by-phrase"),
            Case("Mary was given the book.", "passive_exceptions", "ditransitive passive"),
            Case("He is said to be rich.", "passive_exceptions", "passive + infinitive"),
            Case("The window was broken.", "passive_exceptions", "adjectival passive"),
            Case("It was written in 1990.", "passive_exceptions", "impersonal passive"),
            Case("She got hurt.", "passive_exceptions", "get-passive"),
            Case("The house is being built.", "passive_exceptions", "progressive passive"),
            Case("The book has been read.", "passive_exceptions", "perfect passive"),
        ),
    ),
    (
        "raising_control",
        (
            Case("John seems to be tired.", "raising_control", "raising subject"),
            Case("There appears to be a problem.", "raising_control", "there raising"),
            Case("John wants to leave.", "raising_control", "subject control"),
            Case("John persuaded Mary to leave.", "raising_control", "object control"),
            Case("John is easy to please.", "raising_control", "tough movement"),
            Case("John is believed to be honest.", "raising_control", "raising passive"),
            Case("She made him leave.", "raising_control", "causative bare"),
            Case("They consider John a friend.", "raising_control", "object predicate"),
        ),
    ),
    (
        "long_distance",
        (
            Case("Who did John see?", "long_distance", "wh object gap"),
            Case("Who did John talk to?", "long_distance", "wh PP gap"),
            Case("Which city did he come from?", "long_distance", "which + PP gap"),
            Case("What do you think he did?", "long_distance", "bridge verb"),
            Case("The book that John said he read was good.", "long_distance", "relative + embedding"),
            Case("She is the one I told you about.", "long_distance", "preposition stranding"),
            Case("How difficult did you say it was?", "long_distance", "degree pied-piping"),
        ),
    ),
    (
        "ellipsis",
        (
            Case("John left and Mary did too.", "ellipsis", "VP ellipsis"),
            Case("John likes tea and Mary coffee.", "ellipsis", "gapping"),
            Case("John ordered tea and Mary coffee.", "ellipsis", "gapping ditransitive"),
            Case("He can swim faster than she can.", "ellipsis", "comparative ellipsis"),
            Case("I like him more than her.", "ellipsis", "comparative NP"),
            Case("John is tall and Mary is, too.", "ellipsis", "predicate ellipsis"),
            Case("Some came early and some late.", "ellipsis", "subject gapping"),
        ),
    ),
    (
        "discourse_markers",
        (
            Case("However, he left.", "discourse_markers", "however"),
            Case("Therefore, she stayed.", "discourse_markers", "therefore"),
            Case("In fact, it was true.", "discourse_markers", "in fact"),
            Case("On the other hand, it could work.", "discourse_markers", "on the other hand"),
            Case("For example, the dog ran.", "discourse_markers", "for example"),
            Case("That is, he left early.", "discourse_markers", "that is"),
            Case("Of course, she agreed.", "discourse_markers", "of course"),
        ),
    ),
    (
        "existential_presentation",
        (
            Case("There is a problem.", "existential_presentation", "there is"),
            Case("There were many people.", "existential_presentation", "there were"),
            Case("There seems to be a mistake.", "existential_presentation", "there seems"),
            Case("Here is the book.", "existential_presentation", "here is"),
            Case("There goes the bus.", "existential_presentation", "there goes"),
            Case("A problem exists.", "existential_presentation", "existential verb"),
        ),
    ),
    (
        "negative_polarity",
        (
            Case("I have never seen it.", "negative_polarity", "never"),
            Case("He did not say anything.", "negative_polarity", "not anything"),
            Case("She barely spoke.", "negative_polarity", "barely"),
            Case("He hardly knew her.", "negative_polarity", "hardly"),
            Case("Not everyone came.", "negative_polarity", "not everyone"),
            Case("No one knew.", "negative_polarity", "no one"),
            Case("I don't know anything.", "negative_polarity", "don't know anything"),
        ),
    ),
    (
        "coordination_asymmetry",
        (
            Case("John ran and jumped.", "coordination_asymmetry", "VP coordination"),
            Case("John ran up the hill and jumped over the fence.", "coordination_asymmetry", "VP + PP coordination"),
            Case("She sang and he danced.", "coordination_asymmetry", "clause coordination"),
            Case("The red and blue cars.", "coordination_asymmetry", "adjective coordination"),
            Case("He is tall and strong.", "coordination_asymmetry", "adjective predicate"),
            Case("To go or to stay.", "coordination_asymmetry", "infinitive coordination"),
        ),
    ),
    (
        "null_elements",
        (
            Case("He is taller than she.", "null_elements", "than + bare pronoun"),
            Case("I like him more than her.", "null_elements", "than + accusative"),
            Case("Who do you think left?", "null_elements", "long-distance wh"),
            Case("The book I read was good.", "null_elements", "reduced relative object gap"),
            Case("She is the one to ask.", "null_elements", "infinitival relative"),
        ),
    ),
)


def run_families(parser: Any) -> dict[str, FamilyResult]:
    """Parse every case in every family; return per-family results."""
    results: dict[str, FamilyResult] = {}
    for family, cases in FAMILIES:
        result = FamilyResult(family=family)
        for case in cases:
            result.total += 1
            report = parser.parse(case.text)
            ok = report.result.completed
            if not ok:
                # Fragments are legitimate: NP / ADVP goals count too.
                for goal in ("NP", "ADVP", "VP"):
                    from .engine import Parser as _P
                    if _P(parser.resources, goal_category=goal).parse(case.text).result.completed:
                        ok = True
                        break
            if ok:
                result.passed += 1
            else:
                result.failures.append(case)
        results[family] = result
    return results


def report(results: Mapping[str, FamilyResult]) -> str:
    lines: list[str] = []
    total = sum(r.total for r in results.values())
    passed = sum(r.passed for r in results.values())
    lines.append(f"=== EXCEPTIONS: {passed}/{total} = {passed/total:.1%} ===")
    for family in sorted(results, key=lambda f: results[f].rate):
        r = results[family]
        lines.append(f"\n[{r.rate:5.0%}] {family}  {r.passed}/{r.total}")
        for case in r.failures[:8]:
            lines.append(f"    FAIL {case.text!r:52} {case.note}")
        if len(r.failures) > 8:
            lines.append(f"    ... +{len(r.failures) - 8} more")
    return "\n".join(lines)


def main() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from .engine import Parser

    data = Path(__file__).resolve().parent.parent / "data"
    parser = Parser.from_dir(data)
    results = run_families(parser)
    print(report(results))


if __name__ == "__main__":
    main()
