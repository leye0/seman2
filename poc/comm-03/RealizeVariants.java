import simplenlg.framework.*;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.*;
import simplenlg.realiser.english.Realiser;

public class RealizeVariants {
    private static String clause(NLGFactory f, Realiser r, String subject) {
        SPhraseSpec c = f.createClause(subject, "be", "large");
        return r.realiseSentence(c);
    }
    public static void main(String[] args) {
        Lexicon lexicon = Lexicon.getDefaultLexicon();
        NLGFactory factory = new NLGFactory(lexicon);
        Realiser realiser = new Realiser(lexicon);
        System.out.println("EN-DEFINITE\t" + clause(factory, realiser, "the car"));
        System.out.println("EN-PRONOUN\t" + clause(factory, realiser, "it"));
        System.out.println("EN-FORMAL\t" + clause(factory, realiser, "the automobile"));
        AdjPhraseSpec adjective = factory.createAdjectivePhrase("large");
        System.out.println("EN-FRAGMENT\t" + realiser.realiseSentence(adjective));
    }
}
