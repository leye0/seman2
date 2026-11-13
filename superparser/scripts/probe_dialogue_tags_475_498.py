"""Source-scope research only: inspect pinned #475 / #498 lexical and rank-one proof."""
import json,signal
from pathlib import Path
from seman_parser.engine import Parser,ParserResources
from scripts.diagnose_novel_parses import select_cases
DATA=Path(__file__).resolve().parents[1]/"data"
PROBES={
475:["So far so good","But now I find that every man before the mast knows more than I do","I find that every man before the mast knows more than I do","every man before the mast knows more than I do","every man before the mast","I do","I don't call that fair","that","do you","call that fair","fair"],
498:["That's your seven hundred thousand pounds","your seven hundred thousand pounds","is it","You're the man for bargains","the man for bargains","ain't you","You're him that never bungled nothing","him that never bungled nothing","that never bungled nothing","never bungled nothing","you wooden-headed lubber","wooden-headed"]}
GOALS={"every man before the mast":"NP","that":"NP","fair":"ADJP","your seven hundred thousand pounds":"NP","the man for bargains":"NP","him that never bungled nothing":"NP","you wooden-headed lubber":"NP","wooden-headed":"ADJP","that never bungled nothing":"REL-CLAUSE","never bungled nothing":"VP"}
def tree(n,source,depth=0):
    if not n:return None
    return {"cat":n.category,"rule":n.rule_id,"text":source[n.start:n.end],"features":n.features.as_dict(),"children":[tree(c,source,depth+1) for c in n.children] if depth<3 else []}
class Timeout(Exception):pass
def timeout(*_):raise Timeout()
def main():
    cases,_=select_cases(500)
    resources=ParserResources.from_dir(DATA)
    for index,fragments in PROBES.items():
        source=cases[index]["source_text"]
        print("DEEP_SOURCE",index,json.dumps(source),flush=True)
        base=Parser(resources,cache_size=0)
        lattice=base._lattice_for_text(source)
        for t in lattice.tokens:
            if t.text.casefold() in ("don't","that's","you're","ain't","now","call","find","knows","never","nothing","fair","wooden","headed"):
                print("DEEP_LEX",json.dumps({"index":index,"word":t.text,"candidates":[[c.surface,c.category,c.span_start,c.span_end,c.features.as_dict()] for c in lattice.candidates if c.span_start>=t.start and c.span_end<=t.end][:45]}),flush=True)
        for frag in fragments:
            goal=GOALS.get(frag,"CLAUSE")
            p=Parser(resources,goal_category=goal,cache_size=0)
            signal.signal(signal.SIGALRM,timeout)
            signal.setitimer(signal.ITIMER_REAL,6)
            try:
                r=p.parse(frag,max_items=50_000,kbest_work_limit=500_000).result
                print("DEEP_PROBE",json.dumps({"index":index,"text":frag,"goal":goal,"completed":r.completed,"tree":tree(r.best(),frag),"budget":r.stats.get("budget_exceeded")}),flush=True)
            except Timeout:print("DEEP_PROBE",json.dumps({"index":index,"text":frag,"goal":goal,"timeout":True}),flush=True)
            finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=="__main__":main()
