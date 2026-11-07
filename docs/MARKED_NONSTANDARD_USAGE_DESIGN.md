# Usages non standards marques — contrat de conception

**Statut : implementation pilote opt-in sur le cas 463 (*Treasure Island*).**
La reconnaissance standard et son score restent stricts. Les deviations sont
des annotations sur des liens de l'arbre choisi, pas des rectifications de la
grammaire ou du lexique.

## Probleme

Le moteur unifie correctement les traits grammaticaux avec des contraintes strictes. Cependant, un roman peut citer une phrase qui **emploie deliberement une forme non standard**. Faire echouer la phrase en entier perd l'information ; rendre `plural` compatible avec `singular` contamine la grammaire. La solution est de **conserver le conflit et le localiser sur la relation syntaxique** qui l'a produit.

Il faut distinguer trois diagnostics, et ne jamais les confondre dans les resultats :

1. `standard` : derivation conforme aux contraintes grammaticales.
2. `nonstandard_attested` : derivation structurelle possible avec un ou plusieurs **ecarts explicites et controles** ; les contraintes de l'anglais standard restent intactes.
3. `unresolved` : aucune derivation complete et fidele ; l'annotation d'un ecart ne remplace pas les autres analyses manquantes.

L'intention de l'auteur ne se deduit **pas** automatiquement d'un accord fautif ou de guillemets synthetiques. `intent=unknown` est la valeur sure ; `intent=deliberate` exige une preuve contextuelle ou une annotation explicite.

## Representation implementee

Un `UsageDeviation` est une annotation immuable sur un **lien d'arbre** (sujet/predicat, tete/complement, etc.), et non une propriete permanente du lexeme `was` ni du lexeme `mothers`. Les spans utilisent des intervalles semi-ouverts ; on conserve le texte analyse, le texte original et la provenance des guillemets transferes.

Exemple de sortie structuree du conflit d'accord du cas 463 (les
`reference_span` sont derives separement par `PreparedCorpusInput.reference_span`,
et ne figurent pas dans la sortie generique du parser) :

```json
{
  "kind": "subject_copula_number_agreement",
  "status": "nonstandard_attested",
  "relation": "subject_to_copula",
  "subject": {
    "surface": "your mothers",
    "analysis_span": [64, 76],
    "features": { "number": "plural", "person": "3", "incidental_subject": "true" }
  },
  "predicate": {
    "surface": "was",
    "analysis_span": [77, 80],
    "features": { "number": "singular", "vform": "finite" }
  },
  "constraint": "subject.number == predicate.number",
  "expected": "plural",
  "observed": "singular",
  "register": "literary_dialogue",
  "intent": "unknown"
}
```

Le schema enregistre les **valeurs reelles** du sujet et de la copule, leurs
spans, leur relation, la regle qui autorise l'analyse, le registre et
`intent=unknown`. Les offsets du texte analyse ne sont pas confondus avec
ceux du texte de reference : `PreparedCorpusInput.reference_span` effectue
la correspondance et renvoie `None` sur les guillemets synthetiques.

## Mecanisme de reconnaissance implemente

- Conserver en premier le parsing **strict** avec la meme unification de traits, le meme lexique et les memes budgets. Aucune relaxation globale de `number`, `person`, `case` ou `subcat`.
- La grammaire `data/marked_usage_grammar.jsonl` est compilee separément,
  superposee a la grammaire de dialogue **uniquement** avec
  `Parser.parse(..., allow_marked_deviations=True)` et une citation reconnue.
  La meme option est transmise par `parse_corpus_case` pour les textes de roman.
- La regle pilote `wh_clause_postposed_relative_marked_plural_subject_singular_copula`
  exige les quatre constituants explicites `WH-NOM + NP[plural,person3]
  + COPULA[singular,finite] + WH-SUBJ`. Elle n'ajoute aucune possibilite
  d'accord dans les autres constructions.
- Le materialiseur preserve la provenance `usage_deviation` de cette regle.
  `ParseResult.usage_deviations()` reconstruit des `UsageDeviation` immuables
  en verifiant les traits reellement presents sur les enfants selectionnes.
  `ParseResult.as_dict()` expose `grammatical_status` et `usage_deviations`.
- Les analyses canoniques et le score des 500 utilisent toujours l'appel
  **sans option**. Le mode marque desactive le cache de parsing pour eviter
  une confusion entre les deux chemins. Un arbre marque n'est pas presente
  comme une derivation standard; les deux resultats sont exposes separement
  par leurs appels.

## Application au cas 463

L'annotation ci-dessus **ne suffit pas** a terminer la phrase. Le parser devra aussi construire de maniere generique :

1. `You've neither sense nor memory` (possession avec `have` contracte et coordination negative).
2. `I leave it to fancy [where ...]` avec l'infinitive rattachee au predicat `leave`, pas au pronom `it`.
3. `where your mothers was that let you come to sea`, avec la relative `that let you come to sea` rattachee a `your mothers`, pas comme attribut de `was`.

La correction de ces constructions sera verifiee sur des phrases independantes. Le seul ecart marque devrait etre l'**accord de nombre**, jamais un rattachement incorrect explique a posteriori comme licence dialectale.

## Tests et garanties de l'implementation pilote

- **Positifs** : `where the sailors were` est strict ; `where the sailors was` peut etre structurellement analysable **uniquement** en mode marque et avec une annotation explicite de conflit ; le cas 463 preserve exactement son original.
- **Negatifs** : `The sailors was` est rejete par le mode strict ; aucun contexte de citation ajoute artificiellement un ecart ; un conflit arbitraire de valence ou de categorie ne devient pas acceptable.
- **Arbres** : comparer les liens et spans du rang 1, les hypotheses alternatives, l'emplacement de l'ecart et la provenance. Les erreurs de relative et d'infinitive ne doivent pas disparaitre sous le marqueur dialectal.
- **Regression** : cas 359, tests d'accord existants, 120/120, 24/24, diagnostic sur la cohorte gelee avec budgets inchanges, CI verte.

**Decision de suivi** : l'arbre marque du cas 463 est complet et ses
rattachements sont controles. Le cas demeure non resolu au sens de
**l'anglais standard strict**. La file canonique conserve cet echec et son
score strict; le curseur peut avancer a 463, avec 473 comme prochaine phrase
deterministe. Aucun credit de completion strict n'est attribue pour 463.
