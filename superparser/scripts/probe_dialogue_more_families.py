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
if __name__=="__main__":probe.run()
