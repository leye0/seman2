# Verdict DLG-02

**PARTIEL — port Python exploitable, contrôle Java non reproductible en l'état.**

Le port Python expose l'état initial, un arbre après chaque token, les actions
lexicales/computationnelles et la sémantique TTR finale ou partielle. Sa petite
grammaire anglaise couvre certains fragments mais ni les préfixes de locuteur
testés ni le français de cette fixture.

Le JAR DyLan versionné échoue en chargeant les ressources du même checkout avec
`Unrecognised label specification`; sa compilation source dépend en outre
d'utilitaires Stanford historiques incompatibles. La comparaison de résultats
ne peut donc pas être déclarée réussie. L'échec, la commande, la révision et la
trace complète sont conservés dans `dylan-java-probe.json`.
