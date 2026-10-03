"""Noyau exécutable des proto-services d'intégration de seman2."""

from .contracts import ContractError, Envelope, ServiceSpec
from .pipeline import IntegrationPipeline, build_pipeline

__all__ = [
    "ContractError",
    "Envelope",
    "IntegrationPipeline",
    "ServiceSpec",
    "build_pipeline",
]
