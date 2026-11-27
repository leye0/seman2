"""Source-preserving English analysis backed exclusively by ERG/ACE."""
from .engine import Parser
from .structural_preanalysis import analyze_paragraph

__all__ = ["Parser", "analyze_paragraph"]
