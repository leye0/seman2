"""Research the reusable grammatical interfaces for dialogue families."""
from scripts import probe_batch_418_roots as probe
probe.PROBES = {
56:(
("Without a story","PP"), ("really","ADV"),
("inquired","V"),("Dora","NP"),("creeping","V"),
("creeping","V-INTRANSITIVE-ING"),("closer","ADV"),
("to me","PP"),("creeping closer to me","VP"),
),
66:(
("Now","ADV"),("David","NP"),("said Mr. Murdstone","SPEECH-TAG"),
("a sullen obdurate disposition","NP"),("is","COPULA"),
("of all tempers","PP"),("the worst","NP"),
("a sullen obdurate disposition is the worst","CLAUSE"),
("a sullen obdurate disposition is, of all tempers, the worst","CLAUSE"),
),
96:(
("Now","ADV"),("David","NP"),("he said","SPEECH-TAG"),
("you must be far more careful today than usual","CLAUSE"),
("you must be far more careful","CLAUSE"),
("far more careful today than usual","ADJP"),
),
200:(
("We are speaking of music","CLAUSE"),("madam","NP"),
("said he","SPEECH-TAG"),("when no longer able to avoid a reply","PP"),
("no longer able to avoid a reply","ADJP"),
("to avoid a reply","VP-NP"),
),
408:(
("In","ADV"),("he","NP"),("shouted","V"),
("he shouted","CLAUSE"),("cursed them for their delay","VP-NP"),
("cursed them for their delay","VP"),
("them for their delay","NP"),
("for their delay","PP"),("he shouted, and cursed them for their delay","CLAUSE"),
),
456:(
("if","CONJ"),("you","NP"),("please","V"),("sir","NP"),
("if you please","CLAUSE"),("if I see anyone, am I to fire?","CLAUSE"),
("if I see anyone, am I to fire","CLAUSE"),
("I see anyone","CLAUSE"),("am I to fire?","CLAUSE"),
),
235:(
("we mean to treat you all","CLAUSE"),
("you must lend us the money","CLAUSE"),
("we have just spent ours at the shop out there","CLAUSE"),
("but you must lend us the money, for we have just spent ours at the shop out there","CLAUSE"),
),
441:(
("Pew","NP"),("they've been before us","CLAUSE"),
("Someone's turned the chest out alow and aloft","CLAUSE"),
),
}
if __name__ == "__main__":
    probe.run()
