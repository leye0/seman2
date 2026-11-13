"""Source-based exploratory rank-one phrase probes for #247/#359.
Only full-source parse_corpus_case and inspected correct attachments qualify
for a historical repair; successful fragment probes are not completions.
"""
from scripts import probe_batch_418_roots as probe
probe.PROBES={
247: (
 ("It is nothing","CLAUSE"),("It is nothing in comparison of Rosings","CLAUSE"),
 ("nothing in comparison of Rosings","NP"),("in comparison of Rosings","PP"),
 ("comparison of Rosings","NP"),("of Rosings","PP"),
 ("my lady","NP"),("I dare say","CLAUSE"),
 ("I dare","CLAUSE"),("dare","V"),("say","V"),
 ("I assure you","CLAUSE"),("assure you","VP"),("you","NP"),
 ("it is much larger than Sir William Lucas's","CLAUSE"),
 ("it is much larger","CLAUSE"),
 ("much larger than Sir William Lucas's","ADJP"),
 ("than Sir William Lucas's","PP"),
 ("Sir William Lucas's","NP"),("Sir William Lucas","NP"),
 ("William Lucas","NP"),("Lucas's","NP"),("Sir","TITLE"),
 ("larger","ADJ"),("much","ADV"),
),
359: (
 ("The family","NP"),
 ("after having been thus occupied for a short time","PP"),
 ("having been thus occupied for a short time","VP"),
 ("having been thus occupied","VP"),
 ("been thus occupied for a short time","VP"),
 ("thus occupied","ADJP"),("for a short time","PP"),
 ("a short time","NP"),("extinguished their lights","VP"),
 ("retired","VP"),("their lights","NP"),
 ("extinguished their lights and retired","VP"),
 ("I conjectured","CLAUSE"),("as I conjectured","CLAUSE"),
 ("to rest","PP"),("to rest","VP-NP"),
 ("The family extinguished their lights","CLAUSE"),
 ("The family retired","CLAUSE"),
)
}
if __name__=="__main__":probe.run()
