import simplenlg.framework.*;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.SPhraseSpec;
import simplenlg.realiser.english.Realiser;
public class RealizeResponse {
  public static void main(String[] args) {
    Lexicon l=Lexicon.getDefaultLexicon(); NLGFactory f=new NLGFactory(l); Realiser r=new Realiser(l);
    SPhraseSpec clause=f.createClause("John","like","Mary");
    System.out.println(r.realiseSentence(clause));
  }
}
