import simplenlg.features.*;
import simplenlg.framework.*;
import simplenlg.lexicon.Lexicon;
import simplenlg.phrasespec.*;
import simplenlg.realiser.english.Realiser;
public class LanguageProbe {
 static void out(String id,Realiser r,NLGElement e){System.out.println(id+"\t"+r.realiseSentence(e));}
 public static void main(String[] args){Lexicon l=Lexicon.getDefaultLexicon();NLGFactory f=new NLGFactory(l);Realiser r=new Realiser(l);
  SPhraseSpec en=f.createClause("the car","be","large");out("en-present",r,en);en=f.createClause("the car","be","large");en.setFeature(Feature.TENSE,Tense.PAST);out("en-past",r,en);en=f.createClause("the car","be","large");en.setFeature(Feature.NEGATED,true);out("en-neg",r,en);
  SPhraseSpec fr=f.createClause("la voiture","être","grande");out("fr-present-through-english",r,fr);fr=f.createClause("la voiture","être","grande");fr.setFeature(Feature.TENSE,Tense.PAST);out("fr-past-through-english",r,fr);fr=f.createClause("la voiture","être","grande");fr.setFeature(Feature.NEGATED,true);out("fr-neg-through-english",r,fr);
 }}
