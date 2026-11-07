# Cas 434 — note de direction nautique et mesure, sans prédicat verbal

> Skeleton Island E.S.E. and by E. Ten feet.

Base : `main` à `eb513a002186b68bfe0edf6343ace4acc0e7a703` ;
cohorte figée SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` ;
WordNet 3.0, `parse_corpus_case` en mode `quote_balanced`, budget de forêt
50 000, budget k-best 500 000, échéance de diagnostic 10 secondes.

## Quel est réellement le texte ?

Dans *Treasure Island*, le texte est une inscription portée au dos d'une
carte, présentée sur des lignes successives :

> Tall tree, Spy-glass shoulder, bearing a point to the N. of N.N.E.
>
> Skeleton Island E.S.E. and by E.
>
> Ten feet.

Le corpus d'évaluation figé réunit les deux dernières notes dans un
seul enregistrement d'analyse : c'est un **record notational** à deux
champs, pas une proposition anglaise où manquerait accidentellement un
verbe fini. **Ne pas retokeniser ou corriger la citation** pour gagner
le test : conserver l'original, les points dans les abréviations et les
spans du témoin. Le groupe *and by* fait partie de la notation nautique
de direction; *Ten feet* est une mesure dont le rattachement géographique
au terrain ne peut être déterminé sans le reste de la carte.

Avant : `no_structural_root`, 84 nœuds de forêt, 4 556 opérations.
La matrice lexicale scindait `E.S.E.` en `E`, `.`, `S`, `.`, `E`, `.` ;
`E.` était lui aussi scindé. Le parseur ne disposait pas de la lecture
conventionnelle de la direction en tant qu'unité notationale. Les deux
noms du lieu et la mesure numérique étaient déjà analysables.

## Correction bornée et générale

1. Une vue lexicale `COMPASS-POINT` regroupe les **seize points attestés
   de la rose des vents**, écrits en notation à points (`E.S.E.`,
   `N.N.E.`, `W.`, etc.). C'est un inventaire fermé standard de
   directions, **pas un dictionnaire de termes tirés de cette phrase**.
   Toutes les lectures d'origine des lettres et de leurs points sont
   préservées, avec leur source et leurs spans. Les formes impossibles
   comme `N.E.W.` ne créent aucune vue de direction.
2. `NOTATION-PLACE-START` est projeté à partir d'une lecture de nom propre
   initiale **seulement lorsque deux directions notées sont présentes**
   dans l'énoncé. Cette borne d'entrée empêche de démarrer une règle
   nominale à chaque NP de la prose, régression observée et corrigée sur
   le témoin de dialogue 359. Le nom propre initial original demeure.
3. Les règles `notation_place_name_single`,
   `notation_place_name_compound`, `notation_compass_and_by_bearing`,
   `notation_reference_with_bearing`, `notation_measure_distance` et
   `clause_notational_bearing_and_measure` assemblent séparément
   la **référence nominale**, la **direction** et la **mesure**.
   `PREP-BY` déjà existant impose le *by* propre à l'expression
   nautique. `NOTATION-STOP`, projeté seulement pour les cas munis de
   directions, impose le **point terminal**, non une virgule libre.

L'interface de sortie reste `CLAUSE`, mais les traits
`utterance_type=notational_record`, `finite_predicate=absent` et
`context_required=true` préviennent explicitement toute interprétation
comme prédicat fini ou instruction implicite.

## Arbre effectivement choisi (rang 1)

```text
CLAUSE clause_notational_bearing_and_measure [0:42]
  NOTATION-REFERENCE notation_reference_with_bearing [0:32]
    NP-NOTATION notation_place_name_compound [0:15] « Skeleton Island »
      NOTATION-PLACE-START « Skeleton »
      PROPER-NOUN « Island »
    NOTATION-BEARING notation_compass_and_by_bearing [16:32]
      COMPASS-POINT « E.S.E. » [16:22]
      COORD « and » [23:26]
      PREP-BY « by » [27:29]
      COMPASS-POINT « E. » [30:32]
  NOTATION-MEASURE notation_measure_distance [33:42]
    NUM « Ten » [33:36]
    N « feet » [37:41]
    NOTATION-STOP « . » [41:42]
```

Les liens `location_name`, `direction`, `quantity` et `unit` sont
distincts. La mesure est un **champ frère** de la référence, et non
un complément attaché arbitrairement au dernier point cardinal.

## Généralisation et contre-exemples

`test_compass_notation.py` contrôle l'arbre sélectionné, les spans,
l'absence de verbe inventé et la provenance des lectures originales.
Positifs indépendants :

- `Beacon Ridge N.N.E. and by N. Fifteen yards.`
- `Black Point W.S.W. and by W. Twenty paces.`

Contre-exemples : point cardinal invalide (`N.E.W.`), mauvais marqueur
(`and with`), unité absente et ponctuation finale non conforme.
Une initiale dans un nom ordinaire (`Mr. E. Smith`) ne peut pas à elle
seule provoquer une analyse notationale.

Le témoin 359 doit conserver `dialogue_unattributed`, 1 472 nœuds
de forêt et 49 842 opérations de reconnaissance; le cas 414 doit
conserver sa racine de fragment elliptique coordonné.

## Résultats vérifiés

Diagnostic officiel exclusif des 500 phrases, comparé ligne par ligne à la
base validée au cas 414 : **472 → 473/500**. **Seul l'index 434 change**
de `no_structural_root` à `complete`. Les 500 SHA-256 des phrases restent
identiques; aucun succès ne disparaît, aucune autre classe d'échec ne
change et aucun nouveau budget de forêt ou k-best n'est dépassé.

- Le témoin 359 garde `dialogue_unattributed`, 1 472 nœuds et le
  même statut `complete`, avec sa saturation ancienne toujours tracée.
- Le témoin 414 conserve sa racine elliptique discursive sélectionnée.
- `test_compass_notation.py` et
  `test_dialogue_contextual_fragments.py` : **8 tests réussis** ;
  contrôles additionnels de discipline statique réussis.
- Smoke canonical/adaptive/dialogue : **PASS**.
- Qualité grammaticale directe : **120/120** annotations structurelles,
  **24/24** contrastes positifs; exactement **9** acceptations négatives
  connues, sans modification des seuils.

La grammaire a d'abord révélé une **régression sur 359** lorsqu'une
nouvelle règle `NOTATION-REFERENCE` commençait par un NP libre. Elle a été
corrigée **avant le diagnostic global** en introduisant une entrée de
nom propre typée `NOTATION-PLACE-START`, activée seulement par une
notation de boussole reconnue. Cette précaution est importante pour
la compositionalité et pour la limite de recherche des dialogues.

La couverture 473/500 est une métrique de reconnaissance sur une cohorte
limitée; elle ne dispense pas d'inspecter les arbres, et le lien matériel
entre la distance et son éventuel référent sur la carte demeure
indéterminé hors de ce contexte.
