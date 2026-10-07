# CORE-04 — Admission épistémique et révision non destructive

Cette POC vérifie qu'une structure ne devient pas une connaissance uniquement
parce que plusieurs analyseurs ou parses répètent la même proposition sur une
seule observation.

Elle exige deux expériences indépendantes sous les seuils configurés. Une
correction indépendante ultérieure crée un nouvel état contesté et conserve la
projection consolidée antérieure avec sa provenance.

Cas négatifs : trois parses d'une seule expérience restent insuffisants et une
projection encore pending est refusée.
