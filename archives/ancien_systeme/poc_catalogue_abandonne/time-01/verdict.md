# Verdict TIME-01

**GO — contrat relationnel interne à développer.**

Les cinq fixtures démontrent qu'un ordre observable peut être représenté comme
ordre partiel sans calendrier : ordre total, branches incomparables et absence
d'ordre restent distincts. Le cycle adversarial est rejeté explicitement.

Les ancres externes restent des objets de provenance. Un timestamp contredisant
l'ordre de source produit un conflit attribué mais ne réécrit pas cet ordre.
Deux timestamps égaux n'introduisent ni simultanéité cognitive ni ordre. Après
retrait de toutes les ancres, la signature relationnelle reste identique dans
chaque fixture.

Cette POC ne prétend pas résoudre les relations sémantiques d'intervalle. Elle
fixe la frontière que TIME-02 et les analyseurs externes devront respecter.
