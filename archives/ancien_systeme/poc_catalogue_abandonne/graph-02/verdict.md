# Verdict GRAPH-02

**GO — contrat strict pour les producteurs exécutables actuels.**

Les adaptations passent un aller-retour Arrow/Parquet et Protobuf déterministe.
Les scores restent absents lorsque le producteur n'en fournit pas ; ils ne sont
jamais inventés. Les analyses textuelles sont explicitement distinguées des
observations audio. Le payload natif canonique demeure accessible, de sorte que
le contrat commun n'impose pas une sémantique interne aux sorties des outils.

Les producteurs empaquetés ensemble possèdent aussi des records séparés et des
sélecteurs source exacts. DyLan reste explicitement indisponible après son échec
de chargement documenté ; aucune fausse sortie n'est synthétisée. Les analyses
déjà publiées dans l'Artifact Arena portent leur véritable ID, build,
configuration, statut et référence d'observation; les sorties historiques sont
identifiées comme sources externes stables, pas comme observations internes.
