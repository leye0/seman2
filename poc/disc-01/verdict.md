# Verdict DISC-01

**PARTIEL — sortie structurée exploitable, validation d'entrée à ajouter.**

Les six textes non vides anglais et français produisent 27 EDUs dont tous les
spans reconstruisent exactement la source. La sortie contient un arbre binaire,
des relations et des nuclearités, mais aucun score sur ces fixtures.

L'entrée vide est silencieusement rendue comme une EDU `[0, 0]` vide. Un
adaptateur devra donc rejeter ou marquer cette sortie avant intégration. IsaNLP
RST reste un analyseur externe : ses relations et nuclearités sont attribuées à
`gumrrg`, jamais converties en vérités cognitives.
