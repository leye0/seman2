# Verdict TIME-08

**GO — HeidelTime et Duckling sont correctement déclassés en analyseurs de
surface externes.**

Toutes leurs sorties historiques conservent producteur, span, type, valeur
native et alternatives disponibles. Aucune analyse n'est sélectionnée comme
vérité cognitive et aucune ne peut créer directement une relation temporelle
interne. La signature des relations épisodiques reste identique avant et après
leur injection.

Les normaliseurs ne modélisent pas E/R/S, la persistance d'état, les ensembles
d'antécédents temporels, le rappel épisodique ni la révision historique. Ces
fonctions restent couvertes par les POC formelles TIME-03 à TIME-07.
