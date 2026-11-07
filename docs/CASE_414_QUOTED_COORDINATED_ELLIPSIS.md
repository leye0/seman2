# Cas 414 — fragment discursif coordonné, sans prédicat explicite

> and now here on my own account, in a manner of speaking.

Base : `main` à `dd5aa85ea126113cf1a9ba366bb1929aaf6d38c2` ; cohorte
figée SHA-256 `cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` ;
WordNet 3.0 ; `parse_corpus_case` en `quote_balanced` ; plafonds inchangés
de 50 000 éléments de forêt, 500 000 unités de k-best et 10 secondes par
phrase dans le diagnostic global.

## Diagnostic : structure et contexte, pas grammaire déficiente

Le cas 414 venait de *Treasure Island* :

> I never sailed along of him; first with England, then with Flint, that's
> my story; and now here on my own account, in a manner of speaking.

Le découpage éprouvé au point-virgule fournit comme **texte source**
`and now here on my own account, in a manner of speaking.` et comme
**texte d'analyse équilibré**
`"and now here on my own account, in a manner of speaking."`.
Les deux guillemets de l'analyse sont **synthétiques et tracés** ;
on ne modifie ni la citation originale, ni l'algorithme de transfert
des guillemets, ni les offsets du passage.

Avant : `roots_without_valid_analysis` ; 271 nœuds de forêt,
9 117 opérations de reconnaissance. Le problème n'est **pas** l'absence
de constituants : les ressources existantes reconnaissent déjà
`now here` (`ADVP`), `on my own account` (`PP`) et
`in a manner of speaking` (`PP`). La séquence n'a simplement **aucun
verbe fini écrit** : le prédicat est elliptique et s'interprète dans le
discours antérieur. Il serait incorrect de convertir *account* ou
*speaking* en prédicat fini pour faire passer la phrase.

## Solution : assemblage discursif à guillemets explicites

Trois règles **uniquement dans `dialogue_grammar.jsonl`** :

1. `dialogue_quoted_coordinated_adverbial_pp_fragment` relie un
   coordinateur initial, un ADVP et un PP dans un fragment dont le
   prédicat reste omis.
2. `dialogue_quoted_fragment_parenthetical_pp` rattache un second PP
   comme incise, séparée par une virgule littérale.
3. `dialogue_unattributed_coordinated_fragment_stop` assemble le fragment,
   un point réel et le guillemet de fermeture sous la **seule interface
   publique `CLAUSE`**, en déclarant `ellipsis=contextual_predicate` et
   `context_required=true`. La structure n'affirme **aucun événement
   lexical** qu'on ne trouve pas dans le texte.

Une vue de la borne de citation,
`OPEN-QUOTE-ELLIPTICAL-COORD`, n'est projetée par `dialogue_lattice`
que lorsque le lattice atteste les éléments **structurels** indépendants
: ouverture de citation, coordinateur adjacent, deux adverbes successifs,
début de PP, virgule et second début de PP avant une citation fermée.
Il n'y a aucune vérification sur les chaînes *now*, *here*, *account*,
*manner*, ni sur le numéro 414. La borne originale `OPEN-QUOTE`, sa
source et sa provenance sont conservées. Cette garde évite d'ouvrir les
nouveaux chemins dans les dialogues longs qui saturent déjà (#359).

Arbre de rang 1, liens et spans testés :

```text
CLAUSE dialogue_unattributed_coordinated_fragment_stop
  [ellipsis=contextual_predicate, context_required=true]
├── QUOTED-ELLIPTICAL-FRAGMENT dialogue_quoted_fragment_parenthetical_pp
│   ├── QUOTED-ELLIPTICAL-FRAGMENT dialogue_quoted_coordinated_adverbial_pp_fragment
│   │   ├── OPEN-QUOTE-ELLIPTICAL-COORD « " »
│   │   ├── COORD « and »
│   │   ├── ADVP advp_adv_adv « now here »
│   │   │   ├── ADV « now »
│   │   │   └── ADV « here »
│   │   └── PP pp_prep_np « on my own account »
│   ├── COMMA « , »
│   └── PP pp_prep_np « in a manner of speaking »
├── SPEECH-STOP « . »
└── CLOSE-QUOTE « " »
```

La reconnaissance est **structurelle** ; le lien avec l'antécédent
discursif (*I never sailed…*) doit encore être résolu par la couche de
contexte future. Le prédicat n'est donc ni rétabli lexicalement ni
prétendu connu de `Parser.parse`.

## Vérification de généralisation et contre-exemples

Quatre tests dans `test_dialogue_contextual_fragments.py` vérifient :

- le cas 414 épinglé, ses spans, sa racine annotée et l'absence de verbe
  fabriqué ; maintien intégral de la provenance de la citation ;
- deux indépendants avec vocabulaire différent :
  `"And later there with my family, for a while."` et
  `"And then here at the station, for the moment."` ;
- refus de la structure pour des séquences sans virgule, sans
  coordinateur initial, sans PP central ou sans point de dialogue ;
- conservation du témoin 359 : racine `dialogue_unattributed`, 1 472
  nœuds de forêt et 49 842 opérations, exactement comme la base.

## Validation de la cohorte figée et des garde-fous

Le diagnostic officiel de 500 phrases, exécuté seul avec les plafonds
existants et comparé ligne par ligne au bilan validé du cas 371, donne
**472/500** contre **471/500**. Le **seul changement de statut** est
l'index 414 (`roots_without_valid_analysis` → `complete`). Les 500
empreintes SHA-256 restent identiques ; il n'y a **aucune régression**
de statut, ni nouveau signalement de saturation de forêt ou de k-best.
Le témoin 222, sensible à la contention de plusieurs diagnostics
simultanés, est bien `complete` dans ce passage exclusif (566 ms).

- Tests spécifiques au fragment : **4/4** ; témoin sensible 359 inchangé.
- Qualité grammaticale directe : **120/120** annotations, **24/24**
  contrastes positifs et les **9** acceptations négatives déjà connues.
- Fumée Layer 1 : succès.
- Suite `unittest discover` : 483 tests exécutés ; un unique échec
  initial portait sur la discipline statique interdisant la comparaison
  textuelle à `"open"`, sans erreur de parsing. La condition a été
  reformulée ; le test statique concerné et les quatre tests du cas 414
  ont tous été relancés et réussis. Les workflows de CI valident
  ensuite l'ensemble publié.

La couverture ne certifie pas à elle seule la qualité de chacun des
autres arbres ; celle du cas 414 a été inspectée par constituants,
rattachements et spans dans les tests dédiés.
