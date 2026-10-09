# Verdict

`GO` — anti-unification exacte de DAG v0.1

Le mécanisme reconstruit ses deux sources, préserve l'ordre, les règles et les
réentrances, apprend les égalités répétées et transfère les substitutions
lexicales sur des phrases nouvelles. Les différences grammaticales protégées
sont rejetées et les candidats presque entièrement variables sont marqués
`trivial`.

Ce GO autorise le POC-02. Il ne valide ni l'alignement approximatif, ni la
compression, ni une abstraction sémantique. Les candidats restent des motifs
grammaticaux paramétriques.

