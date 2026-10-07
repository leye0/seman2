# RUN-03 — Ingestion discursive bottom-up inter-époques

Cette POC sélectionne par curriculum une vraie question et une vraie réponse
dans les Parquet canoniques Stack Overflow. Les deux tours deviennent deux
observations successives du même discours. Le texte HTML natif, les coordonnées
et les locuteurs restent attribués à la source; votes, réponse acceptée et rang
d'échantillonnage n'entrent pas dans l'Artifact Arena.

Chaque tour traverse le runtime cognitif complet. L'état final dépend
causalement des deux `source-record`, et ni retrieval ni Soar ne relisent le
corpus. La POC exécute aussi une baseline continue, une interruption après la
question, un checkpoint atomique, une restauration puis la réponse; les arènes
et schedulers finaux doivent être strictement identiques.
