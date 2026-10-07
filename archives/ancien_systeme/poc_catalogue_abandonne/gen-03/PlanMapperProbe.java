import simplenlg.features.*; import simplenlg.framework.*; import simplenlg.lexicon.Lexicon; import simplenlg.phrasespec.*; import simplenlg.realiser.english.Realiser;
public class PlanMapperProbe {
 static void out(String id,Realiser r,NLGElement e){System.out.println(id+"\t"+r.realiseSentence(e));}
 public static void main(String[] x){Lexicon l=Lexicon.getDefaultLexicon();NLGFactory f=new NLGFactory(l);Realiser r=new Realiser(l);
  out("P1",r,f.createClause("the car","be","large"));
  SPhraseSpec p2=f.createClause("Alice","inspect","the car");p2.setFeature(Feature.TENSE,Tense.PAST);out("P2",r,p2);
  SPhraseSpec p3=f.createClause("Alice","access","the vault");p3.setFeature(Feature.NEGATED,true);out("P3",r,p3);
  SPhraseSpec a=f.createClause("the car","be","large"),b=f.createClause("the car","be","parked");DocumentElement paragraph=f.createParagraph();paragraph.addComponent(f.createSentence(a));paragraph.addComponent(f.createSentence(b));System.out.println("P4\t"+r.realise(paragraph).getRealisation());
 }}
