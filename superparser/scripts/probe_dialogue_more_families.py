"""Independent proof availability for another parallel dialogue batch."""
from scripts import probe_batch_418_roots as probe
probe.PROBES={
157:(
("My overhearings","NP"),("were","COPULA"),("more","DEGREE"),
("to the purpose","PP"),("than","CONJ"),("yours","NP"),
("Eliza","NP"),("said Charlotte","SPEECH-TAG"),
("My overhearings were more to the purpose than yours","CLAUSE"),
),
200:(
("We are speaking of music","CLAUSE"),("madam","NP"),
("said","V"),("he","NP"),("when","CONJ"),("no","NEG"),
("longer","ADV"),("able","ADJ"),("to","TO"),
("avoid","V"),("a reply","NP"),("avoid a reply","VP-NP"),
("said he","SPEECH-TAG"),
),
445:(
("That is all clear","CLAUSE"),("and","COORD"),
("I dare say","CLAUSE"),("true enough","ADJP"),("true","ADJ"),
("enough","ADV"),("replied Dr. Livesey","SPEECH-TAG"),
),
466:(
("Ah","INTERJ"),("well","ADV"),("my son","NP"),
("you praise your stars","CLAUSE"),("he's dead","CLAUSE"),
("praise your stars","VP"),("said Silver","SPEECH-TAG"),
),
}

# Next historical dialogue families: original source substrings only.
# Fragment success is never promoted to full-corpus completion; the
# full source still goes through parse_corpus_case in the 500-case gate.
probe.PROBES.update({
96: (
    ("Now", "ADV"), ("David", "NP"), ("he said", "SPEECH-TAG"),
    ("I saw that cast again as he said it", "CLAUSE"),
    ("you", "NP"), ("must", "MODAL"), ("be", "COPULA"),
    ("far", "ADV"), ("more", "DEGREE"), ("careful", "ADJ"),
    ("far more careful", "ADJP"), ("today", "ADV"),
    ("than usual", "PP"), ("be far more careful today than usual", "VP"),
    ("you must be far more careful today than usual", "CLAUSE"),
),
237: (
    ("But surely", "ADVP"), ("But", "COORD"), ("surely", "ADV"),
    ("I", "NP"), ("may", "MODAL"), ("enter", "V"),
    ("his county", "NP"), ("with impunity", "PP"), ("rob", "V"),
    ("it", "NP"), ("of a few petrified spars", "PP"),
    ("without his perceiving me", "PP"),
    ("his perceiving me", "NP"),
    ("I may enter his county with impunity", "CLAUSE"),
    ("rob it of a few petrified spars without his perceiving me", "VP"),
    ("I may enter his county with impunity, and rob it of a few petrified spars without his perceiving me", "CLAUSE"),
    ("said she", "SPEECH-TAG"),
),
441: (
    ("Pew", "NP"), ("he cried", "SPEECH-TAG"),
    ("they've been before us", "CLAUSE"),
    ("Someone", "NP"), ("'s", "AUX"), ("turned", "V"),
    ("the chest", "NP"), ("out", "ADV"),
    ("alow and aloft", "ADVP"), ("out alow and aloft", "ADVP"),
    ("Someone's turned the chest out alow and aloft", "CLAUSE"),
),
229: (
    ("My dear", "NP"), ("do not give way to such gloomy thoughts", "CLAUSE"),
    ("Let us hope for better things", "CLAUSE"),
    ("Let", "V"), ("us", "NP"), ("hope for better things", "VP"),
    ("Let us flatter ourselves that I may be the survivor", "CLAUSE"),
    ("I may be the survivor", "CLAUSE"),
    ("flatter ourselves that I may be the survivor", "VP"),
),
475: (
    ("So far so good", "ADVP"), ("So far", "ADV"), ("so good", "ADJP"),
    ("every man before the mast", "NP"), ("before the mast", "PP"),
    ("every man before the mast knows more than I do", "CLAUSE"),
    ("I find that every man before the mast knows more than I do", "CLAUSE"),
    ("But now I find that every man before the mast knows more than I do", "CLAUSE"),
    ("I don't call that fair", "CLAUSE"),
    ("do you", "CLAUSE"), ("call that fair", "VP"),
),
498: (
    ("That's your seven hundred thousand pounds", "CLAUSE"),
    ("is it", "CLAUSE"), ("You're the man for bargains", "CLAUSE"),
    ("ain't you", "CLAUSE"),
    ("You're him that never bungled nothing", "CLAUSE"),
    ("you wooden-headed lubber", "NP"),
),
})

# More multi-sentence witnesses: subspan proofs only, never aggregate wins.
probe.PROBES.update({
99: (
    ("As long as you are here", "CLAUSE"),
    ("my pet", "NP"),
    ("I shall come over every week of my life to see you", "CLAUSE"),
    ("I shall come over", "CLAUSE"),
    ("every week of my life", "NP"),
    ("to see you", "VP"),
    ("One day, every week of my life", "NP"),
),
223: (
    ("There has been many a one", "CLAUSE"),
    ("I fancy", "CLAUSE"),
    ("overcome in the same way", "VP"),
    ("many a one", "NP"), ("in the same way", "PP"),
    ("I wonder who first discovered the efficacy of poetry in driving away love", "CLAUSE"),
),
464: (
    ("There", "INTERJ"), ("Wot did I say", "CLAUSE"),
    ("did I say", "CLAUSE"), ("No good'll come o' that", "CLAUSE"),
    ("No good", "NP"), ("'ll", "MODAL"),
    ("come", "V"), ("o' that", "PP"), ("I said", "CLAUSE"),
),
})

if __name__=="__main__":probe.run()
