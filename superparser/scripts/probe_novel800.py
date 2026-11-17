"""Bounded source and lexical proof diagnostics for earliest Novel-800 failures."""
import os
from pathlib import Path
from scripts import novel_ladder as ladder
from research.verbnet_lr.corpus_pipeline import parse_corpus_case
from seman_parser.engine import Parser,ParserResources

ROOT=Path(__file__).resolve().parents[1]
FRAGMENTS={
702:["From thence","we proceeded to Oxford","to Oxford","From there","we proceeded to Paris"],
704:["Had my eyes deceived me?","my eyes","deceived me","his eyes","Had his eyes deceived him?"],
705:["This professor","was very unlike his colleague","very unlike his colleague","unlike his colleague","his colleague","This teacher was very unlike her colleague."],
730:["So with the second.","with the second","the second","So with the third."],
735:["In the meantime","I had a better chance","as I supposed","before me","a better chance"],
708:["Your affectionate and afflicted father","Alphonse Frankenstein","affectionate and afflicted father","Your affectionate","and afflicted father"],
713:["Geneva","May 12th","May 12th, 17--.","17--","Geneva, May 12th"],
718:["To go instantly to Geneva","come with me","to order the horses","instantly to Geneva","me, Henry"],
721:["The most violent storm","hung exactly north of the town","north of the town","over the part of the lake","the part of the lake","which lies between the promontory of Belrive and the village of Copet","between the promontory of Belrive and the village of Copet"],
732:["I thought perhaps Dr. Livesey--","I thought perhaps","I began","Dr. Livesey","thought perhaps Dr. Livesey"],
749:["Had there been a breath of wind","there been a breath of wind","we should have fallen on the six mutineers","the six mutineers","who were left aboard with us","slipped our cable","away to sea","we should have fallen on the six mutineers who were left aboard with us"],
763:["I beg, sir","he returned respectfully","that you will be seated, and allow me to do this","you will be seated","allow me to do this","to do this"],
791:["Wickham, perhaps, is my favourite","Wickham is my favourite","I think I shall like your husband quite as well as Jane's","I shall like your husband quite as well as Jane's","quite as well as Jane's","your husband"],
795:["Vain indeed must be all her attentions","all her attentions","vain and useless her affection for his sister and her praise of himself","her affection for his sister","her praise of himself","if he were already self-destined for another","self-destined for another"],
797:["Thank you","said Lydia","for if you did, I should certainly tell you all, and then Wickham would be angry","if you did","I should certainly tell you all","then Wickham would be angry","for if you did"],

}
def main():
  sources=ladder.load_sources()
  manifest=ladder.read_json(ROOT/'research/novel_800_exploration/novel-800-candidate-cohort.json')
  cases={c['ladder_index']:c for c in ladder.resolve(manifest,701,sources)}
  parser=Parser(ParserResources.from_dir(ROOT/'data',wordnet_dict=Path(os.environ['WORDNET_DICT'])),cache_size=0,max_items=50000)
  parser.parse("John opened the box.")
  for idx,parts in FRAGMENTS.items():
    case=cases[idx]
    prepared,lattice,result=parse_corpus_case(parser,case,max_items=50000,kbest_work_limit=500000)
    best=result.best()
    print("CASE",idx,repr(case['source_text']),"status",result.completed,"root",best.rule_id if best else None,"stats",str({k:result.stats.get(k) for k in ('budget_exceeded','kbest_budget_exceeded','forest_nodes','partial_states','structural_root_nodes')}),flush=True)
    print("COMPONENTS",idx,prepared.structural_constituents,flush=True)
    for token in lattice.tokens:
      candidates=lattice.covering(token.start,token.end)
      print("TOKEN",idx,repr(token.text),[(c.category,c.lemma,c.features.as_dict()) for c in candidates[:8]],flush=True)
    for phrase in parts:
      found={}
      for category in ("NP","PP","VP","CLAUSE","ADJP","ADVP"):
        try:
          result=parser._vector_grammar.parse_lattice(parser._lattice_for_text(phrase),goal_category=category,max_items=3500,kbest_work_limit=35000,beam=parser.beam)
          b=result.best()
          if b:found[category]={"rule":b.rule_id,"feat":b.features.as_dict(),"budget":bool(result.stats.get("budget_exceeded"))}
        except Exception as exc: found[category]=type(exc).__name__+":"+str(exc)
      print("FRAGMENT",idx,repr(phrase),found,flush=True)
if __name__=="__main__":main()
