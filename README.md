# seman2

Seman2 vise un agent conversationnel symbolique et développemental non-LLM.
Le modèle apprend un univers relationnel et des formes distribuées à partir
d'expériences linguistiques ordonnées; il répond ensuite uniquement depuis les
mémoires qu'il a réellement construites.

L'unique architecture active est
[`plans/architecture_cognitive_developpementale.md`](plans/architecture_cognitive_developpementale.md).
Elle définit les composants, propriétaires d'état, contrats L0→L7, dépendances,
boucles autorisées, flux ingestion/chatbot, mémoire, Soar et persistance.

Le programme de preuves actif est
[`plans/required_poc.md`](plans/required_poc.md). Il repart de zéro. Une POC doit
consommer le stock réellement produit par le niveau inférieur; une fixture qui
instancie directement un objet haut niveau est un test unitaire.

## État actuel

- l'ancien catalogue de 103 POC et son runtime sont archivés sous
  `archives/ancien_systeme/`;
- les anciennes architectures sont archivées sous `plans/archives/`;
- aucune ancienne qualification `GO` n'est active;
- les modules sous `seman2_runtime/` ne sont admis dans le système intégré que
  dans la mesure exacte démontrée par les POC `SYS-*` successivement vertes;
- `SYS-01` est validée par 19 contrôles : six expériences réelles traversent
  l'ingestion générique et ACE/ERG, avec alternatives, mot inconnu, `no-parse`,
  timeout, panne, budgets mesurés, ledger fermé et replay déterministe;
- `SYS-02` est validée par 28 contrôles : elle consomme exclusivement le ledger
  SYS-01 fermé et vérifié, compose toute la matière MRS en L2 sans perdre les
  constantes natives, conserve pertes et portée, puis ferme les branches L3
  sans sélectionner de vérité;
- `SYS-03` est validée par 16 contrôles : deux épisodes L4 réels produisent une
  relation consolidée, une forme distribuée décodable et une réponse interne
  traçable; la biographie témoin répond `unknown`.
- `SYS-04` est validée par 22 contrôles : 12 expériences traversent L0→L4,
  une transformation L5 est induite avec exception, puis prédit sur un acteur
  et un objet réservés avant que leur outcome réel soit ingéré.
- `SYS-05` est validée par 21 contrôles : 23 candidats L2 réels produisent des
  cadres E/R/S, contraintes Allen et réseaux Z3; l'anaphore et la coréférence
  restent branchées, les contradictions restent visibles et les états
  `closed → open → closed` demeurent interrogeables.
- `SYS-06` est validée par 20 contrôles : situations, épisodes et mémoire
  temporelle réels produisent quatre identités et neuf facettes. La continuité
  classe les antécédents sans résoudre arbitrairement les pronoms; les
  propriétés rapportées restent dans les contextes attribués à Maya et Amira
  et ne deviennent pas des propriétés mondiales.
- `SYS-07` est validée par 24 contrôles : une ambiguïté L3 réelle provoque un
  opérateur d'impasse dans Soar, un retrieval borné soutenu par les mémoires
  épisodique, temporelle et discursive, puis une sélection SML qui cite les
  candidats comparés sans engager cette identité comme vérité.
- `SYS-08` est validée par 29 contrôles : cinq scénarios réels produisent un
  pattern général et des spécialisations L5, puis Soar choisit le bon pattern
  sur deux combinaisons réservées avant leurs outcomes. L'exactitude passe de
  `0.5` pour l'ablation par majorité à `1.0`; les feedbacks L2→L4 produisent
  ensuite un concept L5 récursif plus abstrait et décodable.
- `SYS-09` est validée par 30 contrôles : treize tours repassent chacun par la
  verticale réelle et construisent quatre QUD, deux propositions, deux
  groundings et une réparation. La correction modifie le ranking sans effacer
  l'histoire; chaque transition dépend d'un vrai cycle Soar et de mémoires
  épisodique, temporelle et discursive limitées au préfixe déjà vécu.
- `SYS-10` est validée par 36 contrôles : deux biographies réellement ingérées
  produisent des réponses différentes aux mêmes questions, l'absence de
  support produit une ignorance explicite, les contradictions une demande de
  clarification, puis un plan L6 est réalisé par SimpleNLG et réingéré en L0.
  Ce réalisateur borné reste la baseline d'intégration définie par
  `plans/Seman2_directive_refactor_generation_linguistique.md`; il ne doit pas
  être étendu par accumulation de templates.

## Commandes actives

```bash
./scripts/seman2 install-tools
./scripts/seman2 fetch-corpus
./scripts/seman2 verify
./scripts/seman2 test-unit
./scripts/seman2 audit-pocs
./scripts/seman2 validate-architecture
```

`audit-pocs` ne transforme pas une POC absente en succès : il rapporte les POC
planifiées, implémentées et réellement exécutables. `validate-architecture`
vérifie le graphe de dépendances actif et ses chemins interdits.

Les dépendances sont installées localement sous `.venv*` et `.local`; les
données volumineuses et résultats reproductibles restent ignorés par Git.

## Archives

Les archives sont consultables pour récupérer une idée, un adaptateur ou une
mesure. Elles n'ont aucune autorité sur le système actif et ne peuvent être
appelées par une commande active sans réintroduction explicite par une POC
`SYS-*`.
