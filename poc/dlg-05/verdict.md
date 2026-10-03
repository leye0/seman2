# Verdict DLG-05

**GO — la représentation commune porte les graphes SDRT attribués.**

Le test conserve unités, spans (dont spans français discontinus), locuteurs,
tours, relations typées, arguments orientés, attaches non locales, liens
inter-tours et structures entrelacées. Le document STAC reste un graphe de
dialogue multi-participants ; ANNODIS reste un graphe discursif écrit sans faux
locuteur ajouté.

Chaque texte d'unité est désormais vérifié contre les tokens pointés et chaque
span discontinu possède une liste de spans caractère correspondante. Les
composantes de fils sont explicitement qualifiées de dérivées, jamais de fils
gold fournis par le corpus.

Cette structure ne doit pas être rabattue sur DISC-01/02 : la sortie IsaNLP
testée là-bas était un arbre de constituants RST binaire, alors qu'ici les
multi-parents, croisements et relations non locales font partie du contrat.
DISRPT fournit des annotations de référence uniformisées, pas un parseur SDRT
symbolique général.
