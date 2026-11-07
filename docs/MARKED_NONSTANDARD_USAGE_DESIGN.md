# Usages non standards marques — contrat de conception

**Statut : proposition architecturale, non implementee.** Elle ne change ni la grammaire, ni le lexique, ni les scores. Cas pilote : 463 (*Treasure Island*).

## Probleme

Le moteur unifie correctement les traits grammaticaux avec des contraintes strictes. Cependant, un roman peut citer une phrase qui **emploie deliberement une forme non standard**. Faire echouer la phrase en entier perd l'information ; rendre `plural` compatible avec `singular` contamine la grammaire. La solution est de **conserver le conflit et le localiser sur la relation syntaxique** qui l'a produit.

Il faut distinguer trois diagnostics, et ne jamais les confondre dans les resultats :

1. `standard` : derivation conforme aux contraintes grammaticales.
2. `nonstandard_attested` : derivation structurelle possible avec un ou plusieurs **ecarts explicites et controles** ; les contraintes de l'anglais standard restent intactes.
3. `unresolved` : aucune derivation complete et fidele ; l'annotation d'un ecart ne remplace pas les autres analyses manquantes.

L'intention de l'auteur ne se deduit **pas** automatiquement d'un accord fautif ou de guillemets synthetiques. `intent=unknown` est la valeur sure ; `intent=deliberate` exige une preuve contextuelle ou une annotation explicite.

## Representation proposee

Un `UsageDeviation` est une annotation immuable sur un **lien d'arbre** (sujet/predicat, tete/complement, etc.), et non une propriete permanente du lexeme `was` ni du lexeme `mothers`. Les spans utilisent des intervalles semi-ouverts ; on conserve le texte analyse, le texte original et la provenance des guillemets transferes.

Exemple precis du conflit d'accord du cas 463 :

```json
{
  "kind": "subject_copula_number_agreement",
  "status": "nonstandard_attested",
  "relation": "subject_to_copula",
  "subject": {
    "surface": "your mothers",
    "analysis_span": [64, 76],
    "reference_span": [63, 75],
    "features": { "number": "plural", "person": "3" }
  },
  "copula": {
    "surface": "was",
    "analysis_span": [77, 80],
    "reference_span": [76, 79],
    "features": { "number": "singular", "vform": "finite" }
  },
  "constraint": "subject.number == copula.number",
  "expected": { "copula_number": "plural", "illustrative_form": "were" },
  "observed": { "copula_number": "singular", "surface": "was" },
  "scope": "attested_literary_dialogue",
  "intent": "unknown",
  "source_evidence": {
    "book_id": 120,
    "case_index": 463,
    "balanced_quote_prefix_is_synthetic": true
  }
}
```

Le champ `illustrative_form` aide a expliquer l'ecart sans **corriger** la citation ou generer une nouvelle hypothese lexicale. La correspondance entre `reference_span` et le passage complet d'origine doit etre validee par la provenance de l'extracteur et non reconstruite a l'aveugle.

## Mecanisme de reconnaissance

- Conserver en premier le parsing **strict** avec la meme unification de traits, le meme lexique et les memes budgets. Aucune relaxation globale de `number`, `person`, `case` ou `subcat`.
- Si une construction contient un conflit local **precisement type** et que le contexte permet un emploi marque, produire une **hypothese alternative**. Celle-ci garde les traits effectivement observes et attache la preuve d'une seule relaxation a la relation concernee. Elle ne doit pas injecter une forme corrigee dans le lattice.
- Le mode marque doit etre explicite et borne (types de conflits autorises, nombre maximal d'ecarts, penalite de rang, preuve contextuelle). Il doit rester accessible par `Parser.parse` : ne pas introduire une seconde entree publique ou contourner `parse_corpus_case`.
- Les arbres stricts sont toujours preferes, a structure equivalente. Un arbre marque dont les autres rattachements sont errones demeure **invalide**.
- Publier separement `strict_completed`, `marked_completed` et la liste des deviations. Le score historique des 500 reste calcule **strictement comme avant** ; annoncer un second score annote distinct, jamais une augmentation implicite du score canonique.
- Les deviations se transmettent a la racine selectionnee avec leur origine locale et leurs spans ; elles restent consultables par les consommateurs semantiques sans etre transformees en « faits grammaticaux ».

## Application au cas 463

L'annotation ci-dessus **ne suffit pas** a terminer la phrase. Le parser devra aussi construire de maniere generique :

1. `You've neither sense nor memory` (possession avec `have` contracte et coordination negative).
2. `I leave it to fancy [where ...]` avec l'infinitive rattachee au predicat `leave`, pas au pronom `it`.
3. `where your mothers was that let you come to sea`, avec la relative `that let you come to sea` rattachee a `your mothers`, pas comme attribut de `was`.

La correction de ces constructions sera verifiee sur des phrases independantes. Le seul ecart marque devrait etre l'**accord de nombre**, jamais un rattachement incorrect explique a posteriori comme licence dialectale.

## Tests et garanties indispensables avant implementation

- **Positifs** : `where the sailors were` est strict ; `where the sailors was` peut etre structurellement analysable **uniquement** en mode marque et avec une annotation explicite de conflit ; le cas 463 preserve exactement son original.
- **Negatifs** : `The sailors was` est rejete par le mode strict ; aucun contexte de citation ajoute artificiellement un ecart ; un conflit arbitraire de valence ou de categorie ne devient pas acceptable.
- **Arbres** : comparer les liens et spans du rang 1, les hypotheses alternatives, l'emplacement de l'ecart et la provenance. Les erreurs de relative et d'infinitive ne doivent pas disparaitre sous le marqueur dialectal.
- **Regression** : cas 359, tests d'accord existants, 120/120, 24/24, diagnostic sur la cohorte gelee avec budgets inchanges, CI verte.

**Decision de suivi** : le cas 463 reste actif et non resolu. Ne pas avancer la file a 473 tant qu'il est en cours d'elaboration ; aucun credit de completion n'est attribue avant l'arbre complet et fidele.
