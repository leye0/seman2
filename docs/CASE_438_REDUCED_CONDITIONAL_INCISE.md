# Cas 438 — incise conditionnelle interne et sujet focalisé

> Now, Mrs. Hawkins, just you run upstairs to your husband and tell him, if possible, nothing about it.

Base : `main` à `8154a6230e5f4635ddad8af650dd07e1850d5665` ;
cohorte figée SHA-256
`cf58d1c58d07171fa18cc0bf4da5ea95bff7d7fc8d167646e38c59b79413e92a` ;
WordNet 3.0, `parse_corpus_case` en mode `quote_balanced`, budget de forêt
50 000, budget k-best 500 000, échéance de diagnostic 10 secondes.

Le texte original de *Treasure Island* ne contient pas de guillemets dans
cet enregistrement, mais la préparation canonique du discours direct ajoute
un guillemet initial et un guillemet final synthétiques. Les offsets et la
provenance du texte original sont conservés ; les deux guillemets font partie
de `balanced_analysis_text`, sans retouche du corpus.

## Diagnostic initial

`roots_without_valid_analysis` : 448 nœuds de forêt, 18 722 opérations
de reconnaissance, aucune analyse de rang 1. La tentative de grammaire
dialoguée trouvait une racine structurelle (519 nœuds), mais ne pouvait
matérialiser d'arbre valide. Un test de décomposition avait montré que
`you run upstairs to your husband and tell him nothing about it` était
analysable, tandis que `tell him, if possible, nothing about it` ne l'était
pas : le parenthétique sépare le destinataire du thème du verbe ditransitif.

L'analyse décomposée de `Now, Mrs. Hawkins, just you run ...` faisait en
outre de `just you` un `np_such` construit comme `DEGREE + NP`, et de
`Mrs. Hawkins` une simple expression nominale préposée. Ce n'est pas la
hiérarchie souhaitée : `Mrs. Hawkins` est une apostrophe à l'interlocutrice,
et `just` est un opérateur de focalisation du sujet de l'instruction.

## Correction générique et bornée

1. `parenthetical_reduced_conditional_adjective` construit l'incise
   `PARENTHETICAL` à partir de **virgule + conjonction conditionnelle +
   adjectif + virgule**. Elle conserve l'ellipse d'une copule dans les
   traits (`conditional=true`, `ellipsis=copular`) sans inventer de verbe.
2. `vp_ditransitive_internal_conditional` insère ce constituant **entre**
   le destinataire et le thème d'un verbe dont la valence
   `subcat=ditransitive` est attestée : `V + NP[recipient] +
   PARENTHETICAL + NP[theme]`. L'incise se rattache au VP, et
   `about it` reste rattaché à `nothing`, jamais à `tell` ni à `him`.
3. `clause_preposed_subject_focus` construit un `CLAUSE` à partir d'un
   adverbe de focalisation nominale lexicalement attesté, d'un sujet
   explicite et d'un VP fini accordé. L'adverbe reste un enfant de la
   proposition : pas de nominal `DEGREE + NP` fabriqué.
4. Afin de ne pas saturer les forêts, `segmentation.py` **ajoute sans
   supprimer** trois vues typées : `COMMA-REDUCED-CONDITIONAL`
   (seulement avec les quatre éléments ponctués attestés),
   `V-DITRANSITIVE-CONDITIONAL` (forme finie ditransitive avant cette
   incise), et `ADV-PREPOSED-SUBJECT-FOCUS` (adverbe de focalisation
   attesté suivi d'un début nominal). Toutes gardent `span`, `source`,
   `sense_ids` et les lectures lexicales originales.

L'ancienne règle dialoguée `dialogue_discourse_vocative_clause` est
réutilisée telle quelle : l'adverbe introducteur `Now` et
`Mrs. Hawkins` sont respectivement un marqueur discursif et une
apostrophe, sans nouveau cas spécial consacré à un prénom ou un lexème.

## Arbre choisi (rang 1)

```text
CLAUSE dialogue_unattributed [0:103]
  DIRECT-SPEECH dialogue_quote_clause_comma [0:103]
    OPEN-QUOTE « \" » [0:1]
    CLAUSE dialogue_discourse_vocative_clause [1:101]
      ADV « Now » [1:4]                  : discourse_marker
      COMMA « , » [4:5]
      NP np_honorific_abbreviation [6:18] « Mrs. Hawkins » : addressee
      COMMA « , » [18:19]
      CLAUSE clause_preposed_subject_focus [20:101]
        ADV-PREPOSED-SUBJECT-FOCUS « just » [20:24] : focus
        NP np_indef_pron « you » [25:28]            : subject
        VP vp_coord_finite [29:101]
          VP vp_prepositional [29:57] « run upstairs to your husband »
            V « run »
            PP pp_adv_prep « upstairs to your husband »
              ADV « upstairs »
              PP pp_prep_np « to your husband »
          COORD « and » [58:61]
          VP vp_ditransitive_internal_conditional [62:101]
            V-DITRANSITIVE-CONDITIONAL « tell » [62:66]
            NP np_indef_pron « him » [67:70]        : recipient
            PARENTHETICAL parenthetical_reduced_conditional_adjective
              [70:84] « , if possible, »               : condition
            NP np_pp_mod [85:101] « nothing about it » : theme
              NP np_indef_pron « nothing »
              PP pp_prep_np « about it »
    COMMA « . » [101:102]
    CLOSE-QUOTE « \" » [102:103]
```

Le terminus est représenté par la catégorie historique `COMMA` pour le
point final ; cela ne change ni la segmentation ni les conditions de
l'incise, qui utilisent exclusivement les **virgules littérales**.

## Vérifications structurelles

`superparser/tests/test_reduced_conditional_parentheticals.py` vérifie
l'arbre sélectionné, la portée des constituants et leurs spans, ainsi que
la conservation de la provenance des vues typées. Positifs indépendants :

- `Now, Mr. Watson, just you go home and give her, if necessary, the letter.`
- `Only you tell her, if possible, the truth.`
- `Just you tell her, if convenient, the truth.`

Contre-exemples : conjonction absente (`possible` sans `if`), virgules
absentes, verbe intransitif (`sleep`) et destinataire absent. Aucune de
ces phrases ne doit recevoir la nouvelle composition ditransitive.

Une première version, dont les nouvelles règles démarraient sur toutes
les virgules, tous les verbes ou tous les adverbes de focus, avait
fait échouer le témoin historique 359. La restriction par vues typées
a été appliquée **avant validation globale** : le témoin retrouve
`dialogue_unattributed`, 1 472 nœuds de forêt et exactement 49 842
opérations, sans nouvelle vue candidate.

## Résultats finaux

Le diagnostic canonique complet, comparé ligne par ligne à la base validée
du cas 434, donne **473 → 474/500**. **Seul l'index 438 change de statut** :
`roots_without_valid_analysis` → `complete`. Son arbre retenu a 537 nœuds
de forêt, 20 963 opérations de reconnaissance et 3 545 unités k-best,
sans dépasser les budgets. Les 500 empreintes SHA-256 de phrases sont
identiques. Aucun ancien succès ni aucune ancienne racine de rang 1 n'est
perdu ou modifié ; aucune nouvelle saturation, aucun nouveau délai.

Les classes résiduelles restent exactement : 13 racines non matérialisées,
8 cas sans racine structurelle, 4 saturations de forêt, 1 délai. Les
anciens 17 succès enregistrés avec avertissement de saturation restent
comptés parmi les succès, conformément au bilan historique.

- Suite complète locale : **491 tests réussis**, incluant les 4 nouveaux
  contrôles structurels de la 438 et le témoin 359.
- Smoke canonical/adaptive/dialogue : **PASS**.
- Qualité grammaticale directe : **120/120** annotations structurelles,
  **24/24** contrastes positifs ; exactement **9** acceptations négatives
  connues, sans modification des seuils.
- La CI principale inclut explicitement le nouveau module de tests ; son
  statut après livraison est à vérifier sur GitHub Actions.
