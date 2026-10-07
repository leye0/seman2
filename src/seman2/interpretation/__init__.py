"""Level 2: deep linguistic analyses and their two coupled projections."""

from .model import (
    AnalysisBundle,
    InterpretationHypothesis,
    InterpretationSegment,
    Projection,
    ProjectionEdge,
    ProjectionNode,
    SourceSpan,
)
from .kqml import LocalTripsTransport
from .trips_adapter import TripsAdapter

__all__ = [
    "AnalysisBundle",
    "LocalTripsTransport",
    "InterpretationHypothesis",
    "InterpretationSegment",
    "Projection",
    "ProjectionEdge",
    "ProjectionNode",
    "SourceSpan",
    "TripsAdapter",
]
