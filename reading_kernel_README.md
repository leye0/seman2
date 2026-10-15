# Seman2 — noyau de lecture incrémentale (micro-POC R0)

Cette expérience teste **un mécanisme opérationnel**, pas un nouveau parseur général complet.
Son objet : comprendre mot après mot **trois structures difficiles**, avec les règles déjà présentes dans `superparser/data/grammar.jsonl`, sans chart, agenda, beam ni exploration de toutes les règles.

## Installation

Depuis la racine du dépôt `leye0/seman2` :

```bash
unzip -o seman2_reading_kernel_poc.zip
cd superparser
PYTHONPATH=. pytest -q tests/test_reading_kernel.py tests/test_reading_kernel_integration.py
python scripts/probe_reading_kernel.py --all --json-out reading_kernel_trace.json
```

La POC ne change **aucun fichier existant** du moteur de production. Elle ajoute :

- `seman_parser/reading_kernel.py` : compilateur d'index de règles et micro-noyau déterministe d'événements ; ne dépend pas du runtime Seman2.
- `seman_parser/reading_kernel_adapter.py` : consomme le vrai lattice WordNet/Seman2, effectue la vraie unification des traits et matérialise des `ChartItem`. **Aucun repli vers le parseur historique.**
- `scripts/probe_reading_kernel.py` : trace chaque consommation, attente, suspension et complétion **effectivement exécutée**, avec compteurs.
- `tests/test_reading_kernel.py` : tests indépendants avec un *mini-extrait* des structures grammaticales existantes ; ces tests **ne prouvent pas** la compatibilité avec la grammaire et WordNet complets.
- `tests/test_reading_kernel_integration.py` : vrais tests sur le dépôt réel, automatiquement ignorés seulement si les ressources réelles sont absentes.

## Ce que le programme fait réellement

### `The recipe Rosa followed failed.`

- `The recipe` : un NP reconnu ; attendre le prédicat principal.
- `Rosa` : signal nominal **à la place** du verbe attendu ; si la grammaire possède la chaîne `NP→NP WH-OBJ`, `WH-OBJ→NP VP-GAP` et `VP-GAP→V`, suspendre le prédicat, démarrer la relative sans marqueur.
- `followed` : lire le verbe selon sa projection de valence, satisfaire la lacune d'objet ; compléter la relative.
- `failed` : reprendre le prédicat principal et fermer la proposition.

### `Are the keys inside the box?`

- `Are` : la position initiale et sa catégorie COPULA activent immédiatement la règle `CLAUSE→COPULA NP PP QMARK`, si elle existe.
- `the keys` → NP, `inside the box` → PP, `?` → clôture.

### `The teacher listed dates, places, and names.`

- `listed` : commencer un prédicat transitif à objet NP.
- `dates` : objet nominal simple ; la virgule signale son extension en liste.
- `places` puis `and names` : prolonger la liste **sans retraiter les éléments déjà consommés**, puis compléter le VP et la proposition.

Les déclencheurs de ces réactions sont compilés à partir de **signatures structurelles des règles**. La logique de *lecture* n'est pas codée sur les mots `Rosa`, `keys`, `dates`, etc. Les catégories/structures sont encore expressément traitées : **ce n'est PAS un compilateur universel des 385 règles**. C'est un banc d'essai pour les opérations à généraliser dans une version ultérieure.

## Contrat d'efficacité

- Une position de lecture active ; un seul chemin construit.
- Chaque catégorie lexicale est indexée une seule fois au début ; consultation par `(position, catégorie)`.
- Les règles sont indexées **une seule fois** par `(LHS, RHS_categories)` à l'initialisation. Aucun parcours des règles à chaque mot.
- Unifications uniquement lors de la complétion de constructions effectivement choisies.
- Pas de retour arrière dans ces cas : si aucune réaction licite n'est disponible, `STOP` avec motif.
- On compte `events`, `consumptions`, `reaction_probes`, `category_probes`, `rule_lookups`, `unifications`, `constructions` et `lexical_feature_checks`. Chaque `COMPLETE` correspond à une vraie unification.
- Les traces de complétion sont attribuées au **dernier mot consommé**, pas au mot suivant.

## Tests exécutés ici

Les six cas (3 originaux + 3 variations) passent contre une grammaire de test réduite, dérivée des signatures réelles : **6 tests de comportement, zéro reprise, 4 à 7 unifications par phrase**. La vérification de rejet et de consultation indexée passe aussi. Il s'agit d'un test du **mécanisme**, pas d'une mesure de couverture du système complet.

**Non exécuté ici :** les tests d'intégration utilisant le WordNet et les 385 règles du dépôt privé. Ils doivent être lancés dans ton environnement. S'ils échouent, examine la trace plutôt que de rajouter des recherches globales ou des fallbacks.

## Limites volontairement explicites

1. Le noyau est actuellement limité à la structure propositionnelle `NP VP`, aux NP élémentaires, à la question copulaire inversée, à la relative objet sans marqueur et aux coordinations nominales par virgules. Il doit **échouer clairement** sur le reste, même si la grammaire générale possède une dérivation valide.
2. Il sélectionne une lecture lexicale dans la classe grammaticale attendue, avec contrôle de la valence ; il ne possède pas encore de mécanisme générique de réparation. Les sens lexicalement équivalents ne créent pas d'arbres concurrents.
3. Les PP ambigus, les relatives plus générales, les coordinations verbales, les phrases passives et les dépendances complexes ne sont pas encore pris en charge. Aucun taux de couverture de 300 phrases n'est revendiqué.
4. Les performances isolées ne sont pas directement comparables aux POC précédentes : la grammaire de test est volontairement minuscule. Mesurer **le mécanisme** sur les trois phrases réelles avant toute extension.
5. La réduction valide des **contraintes syntaxiques** ; elle ne prouve pas la plausibilité linguistique ni la résolution sémantique.

## Décision après les tests d'intégration

Si les trois phrases réelles passent avec quelques complétions et zéro recherche, conserver le noyau et généraliser l'inférence des déclencheurs à partir de la grammaire. Si l'une échoue, réparer **le point d'attente précis** révélé par la trace. Interdiction de ressusciter une exploration combinatoire pour masquer une lacune du noyau.
