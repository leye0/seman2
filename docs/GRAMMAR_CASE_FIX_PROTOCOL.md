# Protocole de correction d'une phrase — Layer 1

**Statut : procédure de référence pour toute correction grammaticale individuelle de Seman2.**
Lire aussi [`../AGENTS.md`](../AGENTS.md) (contrat obligatoire),
[`RUN_CURRENT_LAYER1.md`](RUN_CURRENT_LAYER1.md) (architecture et tests) et
[`CURRENT_RESEARCH_HANDOFF.md`](CURRENT_RESEARCH_HANDOFF.md) (priorités actuelles).
En cas de désaccord, le code de `main` et le contrat d'`AGENTS.md` prévalent.

## Ce qui constitue une correction terminée

Une phrase reconnue (`completed=True`) **n'est pas nécessairement bien analysée**.
La correction n'est terminée que lorsque **tous** ces points sont démontrés :

- [ ] **Arbre choisi complet et grammaticalement juste**, pas uniquement une
  racine syntaxique ou un arbre plausible parmi les alternatives. Les
  constituants sont aux bons niveaux; les propositions, sujets, prédicats,
  objets, compléments, subordonnées et incises ont les bonnes relations.
- [ ] **Rattachements exacts**, démontrés par les catégories, `rule_id`, enfants
  et spans de l'arbre sélectionné : prépositions, relatives, adverbes,
  gérondifs, infinitifs, coordinations, négations, etc. Aucun rattachement
  « approximatif » accepté simplement parce que la phrase est reconnue.
- [ ] **Contraintes linguistiques respectées** : personne, nombre, temps,
  aspect, voix, forme verbale, valence, sélection des compléments, ordre,
  ponctuation et portée des modificateurs selon le phénomène corrigé.
- [ ] **Preuves lexicales et provenance intactes** : aucune catégorie inventée
  sans justification; toutes les lectures/sens originaux, les traits, spans,
  sources et identifiants de sens restent accessibles dans le lattice.
  Les vues lexicales supplémentaires, si nécessaires, doivent être justifiées
  et ne doivent pas éliminer les alternatives d'origine.
- [ ] **Règle généralisable**, compositionnelle et suffisamment contrainte.
  Ne pas faire reconnaître une seule citation par un traitement spécial de
  sa chaîne; ne pas affaiblir globalement les contraintes pour gonfler la
  couverture.
- [ ] **Tests positifs et négatifs** : arbre réellement sélectionné sur la
  phrase cible + au moins un exemple positif indépendant et un contraste
  incorrect pertinent. Les tests vérifient les relations et les spans, pas
  seulement `completed`.
- [ ] **Aucune régression établie** : autres arbres corrects, hiérarchie des
  alternatives, dialogues/guillemets, tests unitaires, qualité annotée et
  cohorte figée préservés. Les nouveaux cas saturés sont des régressions,
  même si le taux de complétion augmente.
- [ ] **Budgets et comparabilité inchangés** : même WordNet 3.0, même
  cohorte de 500 cas, même préparation `QUOTE_BALANCED`, même route publique,
  mêmes limites de recherche. Toute exception doit être explicitement
  approuvée et mesurée séparément, jamais glissée dans une correction.
- [ ] **Rapport et CI** : diagnostic initial, cause, arbre après correction,
  contrôles et écarts avant/après documentés; CI correspondante verte.

## Démarche rapide : ordre obligatoire des vérifications

### Choisir la prochaine phrase : **aucune sélection manuelle**

Le prochain cas n'est **jamais** choisi après exploration de plusieurs
phrases, selon sa difficulté ou sa promesse de gain. L'ordre est
**déterministe** : lire [`GRAMMAR_CASE_QUEUE.json`](GRAMMAR_CASE_QUEUE.json),
prendre le premier cas non résolu d'index strictement supérieur au dernier
index tenté, puis revenir au début de la cohorte s'il n'y en a plus.

```bash
PYTHONPATH=superparser python -m scripts.next_grammar_case
```

Après la correction du cas 354, la prochaine phrase est **370**. Même si
elle s'avère complexe, ne pas prospecter d'autres candidates. Si le cas est
bloqué, **documenter le blocage**, conserver ce cas dans la file et avancer
le curseur pour la prochaine demande; il sera revisité au prochain tour.
Après chaque diagnostic global de 500 phrases, mettre à jour **dans le même
commit** la file de cas non résolus, `completed_count`, `validated_commit` et
`last_attempted_index`. Ne pas relancer les 500 analyses juste pour choisir
un cas : la file est l'état issu du dernier bilan validé.

### 0. Fixer le point de départ (avant de coder)

1. Relever le SHA exact de `main`, vérifier les modifications en cours et
   consulter les règles de `AGENTS.md`. Ne pas écraser le travail d'autrui.
2. Réutiliser le même dossier WordNet **3.0** et les dépendances déjà en place;
   ne pas les retélécharger pour chaque phrase.
3. Garder un bilan initial *par index*, pas seulement `467/500` ou un total
   global. Consigner le statut de la cible et les autres échecs connus.

### 1. Diagnostiquer une seule phrase, puis ses constituants

1. Utiliser la cohorte épinglée de `scripts.diagnose_novel_parses.select_cases`
   et **uniquement** `parse_corpus_case(parser, case)` pour toute phrase
   Gutenberg : cette fonction conserve l'origine, les guillemets transférés
   et les offsets. Ne pas appeler `Parser.parse(case["text"])` à la place.
2. Afficher le texte d'origine, `prepared.analysis_text`, la matrice lexicale,
   les statistiques et les 2–3 meilleurs arbres **avec spans et `rule_id`**.
3. Classer l'échec *avant* de changer la grammaire : lexème/forme absent;
   sous-constituant manquant; trait ou valence incompatible; rattachement
   erroné; arbre existant mais mal classé; forêt/k-best saturé ou délai.
   La saturation ne prouve pas qu'une construction est grammaticalement
   impossible.
4. Isoler des sous-constituants (`NP`, `PP`, `VP`, etc.) pour un diagnostic
   local, puis **revenir impérativement au parse complet de la cohorte**
   pour valider la correction. Une sous-analyse réussie ne suffit pas.
5. Chercher d'abord la règle et l'entrée lexicale existantes (`rg`), puis
   la condition précise qui empêche la combinaison souhaitée.

Commande directe d'inspection (depuis la racine du dépôt) :

```bash
export WORDNET_DICT=/chemin/vers/wordnet3/dict
PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m scripts.audit_novel_tree_quality \
  --indices 202 --wordnet-dir "$WORDNET_DICT" \
  --alternatives 3 --lexical-audit
```

Remplacer `202` par l'index ciblé; retirer `--lexical-audit` après le premier
diagnostic si le volume de sortie gêne. L'audit passe par
`parse_corpus_case`, la cohorte complète de 500 étant seulement **chargée**,
pas parsée en entier.

### 2. Appliquer la modification minimale qui explique le défaut

1. Modifier les données lexicales si une vraie lecture manque; modifier les
   règles si c'est une combinaison syntaxique qui manque; modifier les scores
   seulement si un arbre correct existe déjà et est mal classé.
2. Préserver les contraintes positives (`requires`, valence, morphologie,
   indices de ponctuation, catégories de compléments) : chaque règle nouvelle
   doit montrer **pourquoi elle ne reconnaît pas** un contre-exemple.
3. Si un candidat ouvre trop de recherches, vérifier d'abord les conditions
   de démarrage contextuelles et les vues lexicales typées *licites*; ne pas
   augmenter les plafonds de forêt/k-best et ne pas ajouter de nouveau moteur.
4. Ne pas convertir un succès de reconnaissance en preuve de correction :
   réinspecter l'arbre **de rang 1**, son ordre de préférence et ses spans.

### 3. Construire immédiatement les tests de la correction

1. **Cible** : assertions sur l'arbre `best()` : constituants, `rule_id`,
   spans exacts, bonne relation parent/enfant et distinctions grammaticales
   qui ont motivé le changement.
2. **Positif indépendant** : même construction, autre vocabulaire et/ou ordre
   permis, pour empêcher une rustine spécifique à la citation.
3. **Négatifs** : formes fléchies interdites, complément de mauvais type,
   ponctuation obligatoire manquante ou portée incorrecte selon le cas.
   Vérifier le rejet ou l'absence de la structure fautive, sans supposer que
   toute phrase isolée ambiguë est inconditionnellement impossible.
4. **Témoins sensibles** : une phrase voisine, un comparatif et, si la règle
   peut ouvrir beaucoup d'arbres, le cas historiquement saturé **359**.
   Comparer les arbres sélectionnés, pas seulement la liste des tests verts.

### 4. Valider en entonnoir, sans répéter les passes coûteuses

**Boucle courte, à chaque itération :**

```bash
# Adapter la classe de tests à la correction en cours.
PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m unittest -q \
  superparser.tests.test_parser_integration.InfinitivalSubjectTemporalInciseTests

# Comparer la cible et le témoin de saturation à budgets constants.
PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m scripts.audit_novel_tree_quality \
  --indices 202,359 --wordnet-dir "$WORDNET_DICT" --alternatives 2
```

**Une fois la solution stable :**

```bash
PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m scripts.smoke_layer1

PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m scripts.validate_direct_grammar \
  --wordnet-dir "$WORDNET_DICT" --out /tmp/seman2-quality.json

# Exécuter aussi l'intégralité des tests documentés dans RUN_CURRENT_LAYER1.md.
```

Le contrôle global existant exige **120/120 annotations structurelles
sélectionnées** et **24/24 contrastes positifs**; il tolère actuellement au
plus **9 acceptations négatives connues**. Ce n'est **pas** une certification
d'arbres entièrement annotés pour ces 120 phrases : les attaches de la cible
doivent être contrôlées explicitement. Ne pas modifier les seuils pour faire
passer la correction.

**Une seule comparaison complète des 500 cas en fin de correction**, sauf
régression détectée nécessitant un second passage. Exécuter exactement la
même commande sur la base et sur la version candidate (ou réutiliser un
rapport de base identifié par son SHA et ses paramètres) :

```bash
PYTHONPATH=superparser WORDNET_DICT="$WORDNET_DICT" \
  python -m scripts.diagnose_novel_parses \
  --wordnet-dir "$WORDNET_DICT" --count 500 \
  --max-items 50000 --kbest-work-limit 500000 \
  --deadline-seconds 10 --out-dir /tmp/seman2-candidate
```

Comparer **les 500 statuts index par index** dans `per_sentence.jsonl` :
nouveaux succès, succès perdus, nouveaux budgets dépassés, délais et
changements de statut. Les délais et saturations sont **inconclusifs sur la
grammaire**, mais restent des régressions opérationnelles potentielles.
Confirmer même SHA de cohorte, WordNet, mode équilibré et limites; ne jamais
comparer seulement le total de phrases « reconnues ».

### 5. Livrer une seule modification cohérente

1. Ajouter un document `docs/CASE_<index>_<sujet>.md` : SHA de départ,
   citation, cause, arbre choisi et attaches critiques, règles/traits,
   exemples positifs/négatifs, résultats avant/après et limites.
2. Si utile, conserver l'arbre avec ses spans et un petit rapport de validation
   dans `docs/` (voir [`CASE_202_TEMPORAL_INFINITIVE.md`](CASE_202_TEMPORAL_INFINITIVE.md)).
3. Un commit cohérent sur `main` selon la politique de travail du propriétaire,
   avec vérification du HEAD avant écriture; pas de déclenchements CI
   expérimentaux répétés pendant le diagnostic. Vérifier le résultat réel
   de la CI après la livraison.
4. Signaler honnêtement toute incertitude, contre-exemple non résolu,
   changement de score ou arbre dont les rattachements restent discutables.

## Astuces apprises du cas 202 (pour économiser du temps)

| Symptôme | Vérification prioritaire | Piège évité |
| --- | --- | --- |
| Une PP ou un gérondif ne se forme pas | Inspecter d'abord **la matrice lexicale** : manque de `PREP`, `-ing`, valence ou traits ? | Écrire des règles pour compenser un lexème absent |
| Des racines apparaissent, mais la phrase demeure invalide | Inspecter `best()`, `rule_id`, les spans et la matérialisation | Confondre reconnaissance et bonne analyse |
| Une règle aide la cible mais casse une phrase comparative | Comparer **l'ordre des arbres**; revoir spécificité et priorité | Placer « scarcely less eager » sous une structure nominale fautive |
| Le cas 359 passe en saturation | Examiner quels démarrages lexicaux/règles ajoutés ouvrent trop de chemins; tester leur retrait **temporaire en mémoire** | Monter les budgets pour cacher l'explosion |
| Une règle semble spécifique à un mot ou à une citation | Ajouter immédiatement un positif indépendant et deux contrastes grammaticaux | Surajustement à une seule phrase |
| Plusieurs essais répètent 500 parsings et la CI | Garder le bilan SHA, faire cible + témoins pendant la boucle; validation globale **à la fin** | Refaire inutilement les passes les plus longues |

Pour le cas 202, le détail des bons rattachements et de la régression de
classement/saturation est consigné dans
[`CASE_202_TEMPORAL_INFINITIVE.md`](CASE_202_TEMPORAL_INFINITIVE.md).
Ce protocole **réduit les recherches redondantes** mais ne remplace pas
une vérification grammaticale rigoureuse; certaines phrases resteront
difficiles.

## Format bref du compte rendu à remettre

```text
Cas / citation / SHA de base / WordNet / paramètres :
Avant : statut, arbre de rang 1, premier défaut :
Cause démontrée et modification générale :
Après : arbre choisi (liens parent-enfant + spans) :
Tests : cible + positifs indépendants + négatifs + témoins :
Global : unités, smoke, 120/120, 24/24, négatifs acceptés :
500 cas : avant -> après, liste exacte des index changés, timeouts, budgets :
Commit main / CI / limites restantes :
```

**Condition d'arrêt :** si l'arbre correct n'est pas démontré, qu'un ancien
succès disparaît, qu'une forêt sature désormais ou que les seuils habituels
échouent, le cas est **en cours** et non « corrigé ». Diagnostiquer, revenir
sur la règle problématique, ou documenter le blocage avant publication.
