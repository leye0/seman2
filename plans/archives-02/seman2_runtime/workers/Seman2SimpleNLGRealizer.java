import simplenlg.features.Feature;
import simplenlg.features.InterrogativeType;
import simplenlg.features.NumberAgreement;
import simplenlg.framework.CoordinatedPhraseElement;
import simplenlg.framework.NLGFactory;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.NPPhraseSpec;
import simplenlg.phrasespec.PPPhraseSpec;
import simplenlg.phrasespec.SPhraseSpec;
import simplenlg.realiser.english.Realiser;

/** Pure surface realizer: every content-bearing lexeme arrives in the plan. */
public final class Seman2SimpleNLGRealizer {
    private static NPPhraseSpec nounPhrase(
        NLGFactory factory, String head, String specifier, String number
    ) {
        NPPhraseSpec phrase = factory.createNounPhrase(head);
        if (!"-".equals(specifier)) {
            phrase.setSpecifier(specifier);
        }
        if ("pl".equals(number)) {
            phrase.setFeature(Feature.NUMBER, NumberAgreement.PLURAL);
        }
        return phrase;
    }

    private static PPPhraseSpec prepositionPhrase(
        NLGFactory factory, String preposition, String head, String specifier, String number
    ) {
        PPPhraseSpec phrase = factory.createPrepositionPhrase();
        phrase.setPreposition(preposition);
        phrase.addComplement(nounPhrase(factory, head, specifier, number));
        return phrase;
    }

    public static void main(String[] args) {
        if (args.length < 1) {
            throw new IllegalArgumentException("intent required");
        }
        Lexicon lexicon = Lexicon.getDefaultLexicon();
        NLGFactory factory = new NLGFactory(lexicon);
        Realiser realiser = new Realiser(lexicon);
        SPhraseSpec clause;
        switch (args[0]) {
            case "answer-location":
                if (args.length != 9) {
                    throw new IllegalArgumentException("answer-location structured subject verb preposition structured object");
                }
                clause = factory.createClause();
                clause.setSubject(nounPhrase(factory, args[1], args[2], args[3]));
                clause.setVerb(args[4]);
                clause.addComplement(prepositionPhrase(factory, args[5], args[6], args[7], args[8]));
                break;
            case "acknowledge-ignorance":
                if (args.length != 3) {
                    throw new IllegalArgumentException("acknowledge-ignorance subject verb");
                }
                clause = factory.createClause(args[1], args[2], null);
                clause.setFeature(Feature.NEGATED, true);
                break;
            case "request-location-clarification":
                if (args.length != 14) {
                    throw new IllegalArgumentException("clarification structured subject copula coordinator and two structured options");
                }
                clause = factory.createClause();
                clause.setSubject(nounPhrase(factory, args[1], args[2], args[3]));
                clause.setVerb(args[4]);
                CoordinatedPhraseElement options = factory.createCoordinatedPhrase(
                    prepositionPhrase(factory, args[6], args[7], args[8], args[9]),
                    prepositionPhrase(factory, args[10], args[11], args[12], args[13])
                );
                options.setFeature(Feature.CONJUNCTION, args[5]);
                clause.addComplement(options);
                clause.setFeature(Feature.INTERROGATIVE_TYPE, InterrogativeType.YES_NO);
                break;
            default:
                throw new IllegalArgumentException("unsupported intent: " + args[0]);
        }
        System.out.println(realiser.realiseSentence(clause));
    }
}
