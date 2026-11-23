# POC indépendant : grammaire à traits et références linguistiques croisées

Statut : expérimental, hors du moteur de Seman2. Aucune modification de `Parser.parse`, des grammaires ou des corpus figés.

## Hypothèse

Le problème ne doit plus être formulé comme « quelle règle reconnaît cette phrase ? », mais « quelles opérations grammaticales et quels traits permettent de construire ce constituant ? ».

Cette expérience combine, **sans confondre leurs niveaux de preuve** :

| Source | Usage dans le POC | Ce qu'elle ne prouve pas |
| --- | --- | --- |
| **UD English EWT** (entraînement externe) | Dépendances attestées, acquisition de classes lexicales candidates (modification adjectivale, PP en *to*, infinitif en *to*) | La sélection plutôt que l'adjonction d'un PP, l'exhaustivité des verbes/adjectifs |
| **Stanza** (analyseur UD préentraîné) | Une analyse contextuelle indépendante de chaque phrase Novel-1000 | Une dérivation HPSG ou un graphe sémantique correct |
| **ERG** | Inventaire des types lexicaux et des noms de classes HPSG, sans conversion forcée | Une unification complète des descriptions TDL, un parse ERG |
| **FrameNet 1.7** | Inventaire des cadres évoquables par une lecture lexicale | Désambiguïsation des sens ou attribution directe des rôles |
| **VerbNet** (asset déjà présent dans Seman2) | Classes verbales candidates | Attribution certaine de l'une de ces classes dans la phrase |
| **WordNet 3.0** | Inventaire des sens pour chaque lemme et catégorie | La sélection du sens en contexte |

Le *A Valency Dictionary of English* est une référence bibliographique pertinente mais son contenu n'est **pas** importé : aucun jeu de données réutilisable n'est fourni ici.

## Architecture à développer

1. **Signature typée** : `HEAD`, `VALENCE`, `MODIFIES`, héritage multiple et unification. Les contradictions refusent une unification. Les valeurs non attestées restent inconnues.
2. **Induction externe** : récupérer les dépendances de UD-EWT **train**, jamais des phrases Novel-1000 à évaluer. Une suite de mots contigus ne constitue pas une preuve de valence.
3. **Lecture de référence** : annoter les hypothèses avec les types ERG et cadres FrameNet/VerbNet/WordNet disponibles. Il s'agit de couches distinctes ; pas de vote majoritaire entre sources de natures différentes.
4. **Analyse indépendante** : Stanza analyse le texte source entier. La segmentation en propositions internes ne coupe ni ne réécrit le texte fourni. Aucun arbre de Seman2 n'est transmis à l'analyseur.
5. **Diagnostic** : sauvegarder l'arbre, chaque hypothèse de trait, son attestation externe et les erreurs. Les cas mal analysés restent visibles.

### Cas décisif

- `extremely averse to delay` : modification adverbiale de l'adjectif **et** groupe prépositionnel en *to*. Ne pas conclure que le PP est sélectionné sur le seul fondement de `obl` ; un ajout peut présenter la même relation UD.
- `prone to errors` : tester le même schéma, avec une autre tête.
- `happy to help` : infinitif en *to*, un type de valence différent. Ni `to` ni les mots de cet exemple ne doivent être injectés dans un patron de phrase.

Le résultat acceptable à terme est une règle atomique réutilisable dont les contraintes sont démontrées par les ressources grammaticales, avec un test négatif. La simple annotation des relations ne suffira pas.

## Comparaison : garder les dénominateurs séparés

Le POC utilise les **1 000 sources immuables de Novel-1000 v3**, mêmes indices et SHA de manifeste, sans les 30 témoins supplémentaires. L'évaluation est en lecture seule.

Ces nombres ne sont **pas interchangeables** :

- `source_covered / 1000` : part du texte dont tous les caractères non blancs sont couverts par la tokenisation.
- `valid_ud_trees / ud_sentences` : intégrité formelle des arbres de dépendance proposés ; une dépendance erronée peut satisfaire ce critère.
- `adjective_to_pp_candidate` : nombre de relations détectées par l'analyseur UD.
- `hypotheses_with_ud_train_evidence` : nombre de ces observations possédant un antécédent grammatical dans UD train, **pas** validation d'une valence lexicale.
- `tokens_with_...` : quantité de tokens ayant des références lexicales disponibles, **pas** qualité de l'analyse.
- Seman2 `ParseResult.completed` : mesure propre au moteur existant, avec ses conditions structurelles et ses contraintes. Ne pas convertir l'intégrité UD en ce score.

Les sorties doivent être relues sur un ensemble indépendant de rattachements annotés, à créer sans utiliser la prédiction du POC comme vérité terrain. Cette première étape est donc un diagnostic de généralisation et un prototype de représentation, **pas une démonstration de supériorité**.

## Réplication

- Tests purs : `PYTHONPATH=superparser python -m unittest -q superparser.tests.test_typed_resource_poc`
- Simulation limitée : `PYTHONPATH=superparser python -m scripts.typed_resource_poc --limit 10 --out-dir /tmp/poc-smoke`
- Novel-1000 entier : `PYTHONPATH=superparser python -m scripts.typed_resource_poc --out-dir /tmp/poc-full`
- CI : `.github/workflows/typed-multisource-novel1000.yml` sur `research/typed-multisource-poc` ; les artefacts conservent `summary.json` et `cases.jsonl`.

Le téléchargement de modèles Stanza n'est pas encore épinglé par somme de contrôle. La version du logiciel et les révisions des autres ressources sont consignées ; pour un benchmark définitif il faudra également verrouiller les fichiers de modèles.

## Origine et droits des données

- ERG : MIT, révision `13b615ab607374ed7cafe753830e23043a22b71d` — https://github.com/delph-in/erg
- UD English EWT : CC BY-SA 4.0, révision `491be069d36e378f67c29f183699eea88308ea42` — https://github.com/UniversalDependencies/UD_English-EWT
- FrameNet 1.7 : CC BY 3.0, archive NLTK vérifiée par SHA-256 — https://framenet.icsi.berkeley.edu/
- WordNet 3.0 : archive NLTK vérifiée par SHA-256 ; fichier de licence WordNet d'origine à conserver — https://wordnet.princeton.edu/
- VerbNet : fichier compilé déjà présent dans Seman2, conserver sa provenance.

Les corpus externes et les modèles ne sont pas copiés dans la branche, mais téléchargés au moment de l'expérimentation. Le code conserve des références et des observations dérivées, pas les bases originales.

## Travaux suivants après le bilan

1. Importer formellement la hiérarchie de types ERG et valider le sous-ensemble TDL réellement compris par notre système.
2. Réconcilier des **preuves de complémentation** (pas de simples `obl`) avec des types héritables. Prendre en compte les sens lexicaux distincts, les PP ajoutés et les prépositions de surface homographes.
3. Construire un parseur à contraintes où `HEAD` et `VALENCE` traversent les règles de modification/composition, avec saturation explicite.
4. Constituer un jeu de rattachements de référence non utilisé pour créer les types ; comparer Seman2 et le POC **sur cette même vérité terrain**, y compris les refus et les erreurs.
5. Supprimer progressivement une famille de patrons spécialisés seulement lorsqu'une règle générique correctement évaluée la remplace.

**Critère de réussite du projet :** réduire la nécessité d'ajouter des patrons lors du passage à un nouveau corpus, tout en augmentant la justesse des rattachements et sans confondre absence de preuve et preuve négative.

## Premier résultat empirique sur une vérité terrain indépendante

La passe UD English EWT **TEST** compare les dépendances Stanza à 2 077 arbres
de référence. Le modèle reçoit les frontières des mots (pas les dépendances ni
les POS). Le premier passage a mesuré **UAS 90,7627 %**, **LAS 88,3478 %**,
**UPOS 96,7721 %** sur tous les tokens, avec alignement complet.
Les opérations adjectivales (correspondance exacte tête/dépendant) :

| Opération | Gold | Prévu | Correct | P | R |
| --- | ---: | ---: | ---: | ---: | ---: |
| ADV qui modifie ADJ | 256 | 232 | 213 | 91,81 % | 83,20 % |
| PP `to` candidat | 18 | 15 | 15 | 100 % | 83,33 % |
| Infinitif `to` candidat | 20 | 32 | 19 | 59,38 % | 95 % |

**Attention :** ceci mesure d'abord Stanza, pas un gain obtenu par le POC.
Les petits effectifs PP et infinitifs limitent fortement la portée de leurs
pourcentages. Aucune conclusion n'est possible sur la vraie sélection
lexicale contre l'adjonction; elle n'est pas annotée par ce test.

Pour éviter de surestimer la qualité, une seconde mesure sur **200 phrases
déterministiquement échantillonnées par SHA-256 d'identifiant** doit fournir le
texte brut, sans frontières de mots, et compter chaque échec d'alignement comme
une erreur. Le rapport enregistre les résultats bruts et ceux avec frontières
de référence *sur les mêmes phrases*. Les échecs de rattachement explicites
seront exportés pour faire une revue linguistique, sans les recycler comme
de nouvelles règles sur mesure.

Le premier exécutable de la mesure a obtenu les chiffres mais échoué en fin
de CI à cause d'un `KeyError` sur un compteur absent à zéro. Correction dans
cette branche : lecture `get("unaligned_sentences", 0)`. Ne pas appeler la
validation complète verte avant le second rejeu.
