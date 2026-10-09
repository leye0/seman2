# Comparaison A/B/C et API proposée

## Matrice de résultats

| Mesure | A — unique | B — deux moteurs | C — trois moteurs |
|---|---:|---:|---:|
| Observations réelles | 849 | 849 | 849 |
| Validation du graphe compact | 1,000 | 1,000 | 1,000 |
| F1 classes de référents | 0,3064 | 0,3064 | 0,3064 |
| Prédictions relationnelles held-out | 0 | 0 | 0 |
| Précision transitions réelles | 0,4091 | 0,4091 | 0,4091 |
| Rappel transitions réelles | 0,0138 | 0,0138 | 0,0138 |
| F1 transitions contrôlées | 1,000 | 1,000 | 1,000 |
| Précision/rappel transfert réel | 0,6667 / 0,6667 | 0,6667 / 0,6667 | 0,6667 / 0,6667 |
| Réduction d'erreur de révision contrôlée | 1,000 | 1,000 | 1,000 |
| Composants incrémentaux | 4 | 4 | 4 |
| p99 maximal par observation | 0,6393 ms | 0,6393 ms | 0,6393 ms |
| Moteurs | 1 | 2 | 3 |
| Dépendances inter-frontières | 0 | 1 | 3 |
| Primitives dupliquées | 0 | 0 | 0 |
| Rayon maximal des échecs constatés | 11 | 6 | 4 |

Les coûts et scores identiques sont intentionnels : le benchmark compare le
découpage, pas trois réimplémentations auxquelles on aurait donné des avantages
différents. La précision nulle de POC-07 signifie ici abstention complète; elle
ne permet pas de revendiquer une bonne exactitude relationnelle.

## Choix provisoire

**B — deux moteurs**. Il crée la séparation minimale entre :

- structure stable : projection, abstraction, composition, MDL et indexation;
- inférence expérimentale : référents, relations, deltas, transitions,
  transfert et révision.

A reste moins coûteux en frontières, mais mélange les NO-GO réels avec le
chemin structural. C isole davantage, mais aucun gain empirique ne compense
encore ses deux frontières supplémentaires. Ce verdict est architectural et
provisoire; il ne transforme pas les NO-GO de POC-07/09 en GO scientifiques.

## Contrat proposé pour la passe 3

```python
@dataclass(frozen=True)
class EvidenceRef:
    observation_id: str
    component_version: str
    source_span: tuple[int, int] | None

@dataclass(frozen=True)
class StructuralEvidence:
    component_id: str
    bindings: Mapping[str, object]
    evidence: tuple[EvidenceRef, ...]

@dataclass(frozen=True)
class VersionedHypothesis:
    hypothesis_id: str
    version: int
    status: Literal["candidate", "active", "retired"]
    support: tuple[EvidenceRef, ...]
    counterexamples: tuple[EvidenceRef, ...]

class StructuralEngine(Protocol):
    def observe(self, graph: ObservationGraph) -> StructuralEvidence: ...
    def consolidate(self) -> tuple[StructuralEvidence, ...]: ...

class InferenceEngine(Protocol):
    def ingest(self, evidence: StructuralEvidence) -> tuple[VersionedHypothesis, ...]: ...
    def predict(self, context: StructuralEvidence) -> tuple[Prediction, ...]: ...
    def revise(self, evidence: EvidenceRef) -> tuple[VersionedHypothesis, ...]: ...
```

`ObservationGraph` et `Component` restent les formats communs. Toute prédiction
doit référencer ses observations et la version exacte du composant; aucun des
deux moteurs ne reçoit de connaissance physique implicite. Cette API est une
proposition à figer seulement pendant la passe 3.
