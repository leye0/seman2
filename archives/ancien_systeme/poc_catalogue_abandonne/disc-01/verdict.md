# Verdict DISC-01

**GO — sortie structurée exploitable avec validation d'entrée explicite.**

Les six textes non vides anglais et français produisent 27 EDUs dont tous les
spans reconstruisent exactement la source. La sortie contient un arbre binaire,
des relations et des nuclearités, mais aucun score sur ces fixtures.

L'entrée vide, que le modèle natif rendrait silencieusement comme une EDU
`[0, 0]`, est rejetée par l'adaptateur avant l'inférence. IsaNLP RST reste un
analyseur externe : ses relations et nuclearités sont attribuées à `gumrrg`,
jamais converties en vérités cognitives.
