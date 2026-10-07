# Verdict SOAR-03

`GO_NATIVE_SOAR_SEMANTIC_AND_EPISODIC_MEMORY` : SMem retourne de vrais LTI et
leurs activations; Epmem encode et reconstruit de vrais états avec score,
identifiant et navigation temporelle. Les formats natifs suffisent au runtime,
mais l'export épisodique analytique devra passer par la base SQLite ou un
adaptateur propre au système.

Le même trajet fonctionne avec un épisode cognitif réel et conserve ses
identifiants externes dans SMem/Epmem et leurs sauvegardes. L'Artifact Arena
demeure la source canonique de provenance.
