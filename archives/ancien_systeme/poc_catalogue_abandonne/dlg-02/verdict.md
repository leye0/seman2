# Verdict DLG-02

**PARTIEL — port Python intégré, contrôle Java non reproductible en l'état.**

Le port Python expose l'état initial, un arbre après chaque token, les actions
lexicales/computationnelles et la sémantique TTR finale ou partielle. Sa petite
grammaire anglaise couvre certains fragments mais ni les préfixes de locuteur
testés ni le français de cette fixture.

Les six analyses sont maintenant des artefacts attribués avec ascendance
complète jusqu'aux sources. La frontière agrégée dépend des six résultats,
y compris les deux échecs natifs; aucune réussite n'est fabriquée pour rendre
le flow uniforme.

Le JAR DyLan versionné échoue en chargeant les ressources du même checkout avec
`Unrecognised label specification`; sa compilation source dépend en outre
d'utilitaires Stanford historiques incompatibles. La comparaison de résultats
ne peut donc pas être déclarée réussie. L'échec, la commande, la révision et la
trace complète sont conservés dans `dylan-java-probe.json`.
