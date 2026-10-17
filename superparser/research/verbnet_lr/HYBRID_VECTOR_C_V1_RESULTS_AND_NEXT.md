# Seman2 Layer 1 — premier hybride grammatical C + forêt vectorielle

Date: 17 octobre 2026. **Travail expérimental uniquement** dans
\`research/verbnet-left-to-right-poc\`. La branche \`main\` et le chemin
de production \`Parser\` n'ont PAS été remplacés.

## Contrat NON NÉGOCIABLE

Chaque analyse réputée complète doit rester un vrai
\`ParseResult / ChartItem\` : arbre de dérivations hiérarchique classique,
\`NP/VP/PP/CLAUSE\`, règles, spans, traits et unification, dépendances
d'ancrage sujet/objet, ambiguïtés et liens vers les candidats lexicaux.
Les événements, agents, patients, instruments, anaphores et changements
d'état ne sont interprétés qu'au Layer sémantique via
\`ParseReport.interpret\`.

Une correspondance de séquence POS, de regex ou de sous-arbre local
ne suffit PAS à classer une phrase entière « analysée ».

## Code construit (vertical slice v1)

1. \`superparser/research/verbnet_lr/hybrid_vector.py\`:
   - \`HybridVectorParser(Parser)\` réutilise le vrai moteur
     \`VectorGrammar\` et toute sa logique de forêt partagée.
   - \`observe(report, source_id, evidence)\` extrait les productions
     **ORIGINALES**, complètes et localement unifiées d'un arbre.
     Le \`source_id\` empêche le double vote. \`candidate\` et
     \`verified\` sont deux provenances différentes; jamais de
     promotion automatique vers \`verified\`.
   - \`HierarchicalPatternMemory\` apprend les alternatives et les
     extensions grammaticales récursives licenciées.
   - \`compile_guidance()\` indexe les règles apprises par leur nombre
     de phrases-témoins et ne **change que l'ordre** de l'agenda
     \`VectorGrammar.first\`. Toutes les productions restent présentes;
     aucune catégorie/lecture/sous-catégorisation n'est supprimée.
   - Le \`ParseResult\` public reste celui du moteur vectoriel canonique.
     Si le chart guidé dépasse son budget, repli explicite sur l'agenda
     original avec les mêmes limites, sans déclarer une dérivation
     potentiellement tronquée comme complète par optimisation.
   - Recompiler les priorités invalide le cache des analyses, afin
     d'éviter un résultat de configuration périmée.

2. \`hierarchical_pattern_memory.py\`: l'option \`emit_trees=True\`
   matérialise maintenant un VRAI \`ChartItem\` grammatical pour chaque
   constituant C revalidé, avec enfants, offsets, traits et exports
   syntaxiques. Par défaut aucun arbre n'est construit pendant le
   matching rapide. Ces \`ChartItem\` C **sont des témoins LOCAUX**;
   leur injection dans la forêt principale et leur validité de
   rattachement global ne sont PAS encore réalisées.

3. Tests:
   - \`test_verbnet_lr_hybrid_vector.py\`: complétion et vrais arbres,
     données lexicales alternatives, rôles sémantiques de base,
     repli sur budget, interdiction de provenance inventée, aucune
     suppression de règles.
   - \`test_verbnet_lr_hierarchical_pattern_memory.py\`: C reconstruit
     un arbre NP de 8 tokens avec deux PP successifs, alors qu'un
     exemple d'entraînement n'en contenait qu'un; contrôle des
     enfants/feuilles et de l'unification.
   - \`benchmark_hybrid_vector.py\`: entraînement sur 50 phrases
     \`dev\`, test sur 50 \`validation\` +20 \`holdout\` sans fuite,
     24 négatives avec leurs 24 contrastes, mêmes ressources.

## Résultats mesurés v1

Workflow hybride vert:
https://github.com/leye0/seman2/actions/runs/39040479561

48/50 phrases de développement passent les assertions disponibles
et deviennent sources **candidates** des règles, non oracles gold.
Le système active 23 règles avec >=2 phrases-support, et change 76
positions dans 7 listes d'agenda catégoriel.

| Sur les mêmes 70 phrases validation/holdout | Référence | Hybride |
|---|---:|---:|
| Analyses complètes | 70 | 70 |
| Assertions disponibles satisfaites | 67 | 67 |
| Arbres principaux identiques | — | 70/70 |
| Exports syntaxiques identiques | — | 70/70 |
| Mêmes catégories lexicales possibles par position | — | 70/70 |
| Même taille de forêt, dérivations et partiels | — | 70/70 |
| Négatives acceptées /24 | **19** | **19** |
| Contrastes positifs complétés /24 | 22 | 22 |

Exécution exemple: p50/p95 environ 9,9/19,8 ms pour la référence
contre 9,0/15,9 ms pour l'hybride, mais ces latences sont des
mesures séquentielles bruitées sur une même petite série; **on ne peut
pas encore conclure à un gain de vitesse**. La qualité n'a pas
augmenté et les **19 fausses acceptations** constituent une grave
limite du moteur de référence. Les assertions internes de ce petit
corpus ne constituent pas une validation linguistique exhaustive.

Les catégories lexicales ont été comparées comme ENSEMBLES par span;
la multiplicité fluctuante de lectures lexicales redondantes est
mesurée séparément. Ne pas prétendre que l'égalité des multiensembles
est garantie.

## Prochaine étape technique précise: réutiliser, pas seulement prioriser

Ce v1 constitue la base conservatrice et reproductible, PAS le meilleur
hybride final. Il faut ensuite construire les vraies accélérations:

**A — Témoins C comme nœuds de forêt partagée.**
Convertir les \`ChartItem\` locaux C revalidés en dérivations alternatives
packées de la même forêt, avec des signatures
\`(span, category, feature-interface, original-rule-id, child-provenance)\`.
Jamais ne remplacer tous les arbres d'un span par un seul arbre; préserver
les alternatives et les sous-catégorisations. Une dérivation accélérée
doit être reconstruisible intégralement avec enfants et exports.
Avant injection, vérifier que la production et les contraintes font
toujours partie de la grammaire courante et que la mémoire ne les a pas
invalidés. Comparer au chart canonique non assisté sur les mêmes données.

**B — Substitution de calcul réelle.**
Ne compter un gain que si le nombre d'expansions chart, d'unifications
répétées ou de matérialisations diminue. Un simple réordonnancement de
l'agenda qui ne modifie pas le travail total n'est PAS encore une
optimisation sémantiquement utile. Garder une extension sûre sans hit;
cache indexé par structure + interface de traits plutôt que surface
de la phrase.

**C — Grammaire discriminante.**
Faire l'audit des 19/24 négatives du parseur vectoriel: POS abusifs,
valence, passif, accord, complément prépositionnel, attachements,
promotion vers CLAUSE, etc. Corriger de manière linguistiquement générale,
sans règles ad hoc; surveiller les 22 contrastes positifs et les 70
assertions annotées. Ne pas promouvoir une règle apprise à « vraie »
seulement parce qu'un parseur permissif l'utilise.

**D — Generalisation hors corpus interne.**
Tester sur de vraies phrases de romans d'autres auteurs, avec
temps plafonné à 500 ms pour exploration, plus un oracle lent de qualité
sur échantillon annoté. Séparer couverture de CLAUSE complète,
constitution locale, vérification de rôles, et troncature. Répéter
benchmark à corpus constant en alternant l'ordre des modes pour
distinguer un gain structurel du bruit chronométrique.

**E — Apprentissage continu.**
Observer les dérivations candidates sans les auto-valider, obtenir
des preuves indépendantes sur échantillon, promouvoir / réviser /
oublier selon fréquence et utilité; aucune phase d'entraînement
séparée n'est nécessaire à l'exploitation future.

## Verdict

**Premier pas réalisé et vérifié : oui, C peut guider le moteur
syntaxique complet sans perdre les arbres classiques.**
**Accélération démontrée : non.**
**Grammaire corrigée : non.**
**Réutilisation de sous-arbres dans la forêt canonique : prochaine
implémentation, pas encore accomplie.**
