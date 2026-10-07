"""Primitives candidates du nouveau système cognitif développemental.

Ce paquet ne constitue pas encore un runtime intégré. Les composants deviennent
actifs uniquement lorsqu'une POC verticale SYS-* les admet.
"""

from .attention_controller import (
    ProgressiveAttentionController,
    ProgressiveRetrievalResult,
    RetrievalControlPolicy,
    RetrievalLevel,
    RetrievalStep,
    RetrievalStopReason,
)
from .cognitive_artifacts import (
    ArtifactArena,
    ArtifactProposal,
    ArtifactStatus,
    ArtifactTypeRegistry,
    ArtifactTypeSpec,
    CognitiveArtifact,
    Residency,
)
from .cognitive_memory import (
    CognitiveMemory,
    MemoryItem,
    MemoryPolicy,
    MemoryTier,
    RetrievalHit,
    RetrievalRequest,
)
from .cognitive_query import (
    AnswerPlan,
    AnswerStatus,
    AutobiographicalResponder,
    RelationalQuestion,
    StateQuestion,
)
from .concept_learning import (
    ConceptInducer,
    InductionPolicy,
    LearnedStructure,
    SpecializationProposal,
    StructuralOccurrence,
    StructureMatch,
)
from .contracts import ContractError, Envelope, ServiceSpec
from .curriculum import (
    CurriculumController,
    CurriculumExperience,
    CurriculumStage,
    EvaluationCriterion,
    EvaluationProbe,
    EvaluationRecord,
    StageDecision,
)
from .developmental_core import (
    ContextFrame,
    ContextKind,
    ContributionTrace,
    DevelopmentalCore,
    DistributedForm,
    EpistemicState,
    EventOccurrence,
    FormFactor,
    IdentityAnchor,
    Polarity,
    QueryResult,
    RelationEffect,
    RelationEffectKind,
    RelationOccurrence,
    RelationalUniverse,
    RoleBinding,
    StateCondition,
    StateEffect,
    StateFacet,
    SituatedFacet,
    TransitionCandidate,
    TransitionResult,
    VectorSymbolicMemory,
)
from .grammatical_composition import (
    ComposedPropositionCandidate,
    MRSGrammaticalComposer,
)
from .formal_composition import (
    ClosedCompositionBatch,
    GenericMRSComposer,
    build_composition_registry,
)
from .hypothesis_system import HypothesisManager, build_situation_registry
from .identity_resolution import (
    IdentityCandidate,
    IdentityProfile,
    IdentityResolutionDecision,
    IdentityResolutionPolicy,
    IdentityResolver,
    MentionOccurrence,
)
from .open_vocabulary import (
    FormEvidence,
    FormInterpretationCandidate,
    InterpretationDecision,
    InterpretationKind,
    LexicalAction,
    ObservedForm,
    OpenLexicalPlaceholder,
    OpenVocabularyBuilder,
    RepairBeam,
    SurfaceEdit,
    UtteranceRepairHypothesis,
)
from .knowledge_system import KnowledgeAdmissionEngine, build_knowledge_registry
from .low_level_system import (
    AceErgAnalyzer,
    AnalysisOrchestrator,
    ClosedAnalysisLedger,
    ExperienceGateway,
    LowLevelPolicy,
    build_low_level_registry,
    lineage_manifest,
)
from .semantic_admission import (
    AdmissionAssessment,
    AdmissionPolicy,
    AdmissionProjection,
    AdmissionStatus,
    EvidenceOccurrence,
    EvidencePolarity,
    SemanticAdmissionLedger,
    SemanticCandidate,
)
from .transformation_learning import (
    TransformationAlternative,
    TransformationLearningEngine,
    build_transformation_registry,
)
from .temporal_system import (
    RelationalTemporalAnalyzer,
    TemporalReasoner,
    build_temporal_registry,
)
from .discourse_identity_system import (
    ContextualIdentityEngine,
    ContextualMentionExtractor,
    build_discourse_identity_registry,
)
from .soar_control_system import (
    BoundedCognitiveRetrieval,
    ControlGoalBuilder,
    SoarExecutive,
    build_soar_control_registry,
)
from .recursive_concept_system import (
    RecursiveConceptEngine,
    build_recursive_concept_registry,
)
from .dialogue_system import (
    DialogueGameboard,
    DialogueTurnInterpreter,
    build_dialogue_registry,
)

__all__ = [name for name in globals() if not name.startswith("_")]
