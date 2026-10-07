import simplenlg.features.*;
import simplenlg.framework.*;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.*;
import simplenlg.realiser.english.Realiser;

public class CapabilityProbe {
  static void out(String id, Realiser r, NLGElement e) { System.out.println(id + "\t" + r.realiseSentence(e)); }
  public static void main(String[] args) {
    Lexicon lex = Lexicon.getDefaultLexicon(); NLGFactory f = new NLGFactory(lex); Realiser r = new Realiser(lex);
    SPhraseSpec present = f.createClause("the car", "be", "large"); out("present",r,present);
    SPhraseSpec past = f.createClause("the car", "be", "large"); past.setFeature(Feature.TENSE,Tense.PAST); out("past",r,past);
    SPhraseSpec neg = f.createClause("the car", "be", "large"); neg.setFeature(Feature.NEGATED,true); out("negation",r,neg);
    SPhraseSpec prog = f.createClause("Alice", "inspect", "the car"); prog.setFeature(Feature.PROGRESSIVE,true); out("progressive",r,prog);
    SPhraseSpec perf = f.createClause("Alice", "inspect", "the car"); perf.setFeature(Feature.PERFECT,true); out("perfect",r,perf);
    SPhraseSpec combo = f.createClause("Alice", "inspect", "the car"); combo.setFeature(Feature.PROGRESSIVE,true); combo.setFeature(Feature.PERFECT,true); out("perfect-progressive",r,combo);
    NPPhraseSpec plural = f.createNounPhrase("the","car"); plural.setPlural(true); SPhraseSpec agr=f.createClause(plural,"be","large"); out("plural-agreement",r,agr);
    SPhraseSpec first=f.createClause("I","inspect",plural); first.setFeature(Feature.TENSE,Tense.PRESENT); out("first-person",r,first);
    CoordinatedPhraseElement coord=f.createCoordinatedPhrase(f.createNounPhrase("the","car"),f.createNounPhrase("the","truck")); SPhraseSpec coordinated=f.createClause(coord,"be","large"); out("coordination",r,coordinated);
    SPhraseSpec main=f.createClause("Alice","leave"); SPhraseSpec sub=f.createClause("the car","be","ready"); sub.setFeature(Feature.COMPLEMENTISER,"because"); sub.setFeature(InternalFeature.CLAUSE_STATUS,ClauseStatus.SUBORDINATE); main.addComplement(sub); out("subordination",r,main);
    SPhraseSpec yn=f.createClause("the car","be","large"); yn.setFeature(Feature.INTERROGATIVE_TYPE,InterrogativeType.YES_NO); out("yes-no-question",r,yn);
    SPhraseSpec who=f.createClause(null,"inspect","the car"); who.setFeature(Feature.INTERROGATIVE_TYPE,InterrogativeType.WHO_SUBJECT); out("who-question",r,who);
    SPhraseSpec incomplete=f.createClause(); incomplete.setVerb("be"); incomplete.setObject("large"); out("missing-subject",r,incomplete);
    SPhraseSpec missingVerb=f.createClause(); missingVerb.setSubject("the car"); missingVerb.setObject("large"); out("missing-verb",r,missingVerb);
  }
}
