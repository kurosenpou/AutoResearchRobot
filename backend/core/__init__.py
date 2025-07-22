#!/usr/bin/env python3
"""
Core modules for OVITO workflow backend
"""

from .elastic_constants import ElasticConstantsProcessor, load_elastic_constants_from_directory
from .thermomechanical import ThermomechanicalProcessor

# OVITO analysis modules (optional imports - require OVITO)
try:
    from .ovito_analysis import (
        DislocationAnalysis, WignerSeitzAnalysis, OvitoGPUConfig,
        save_dislocation_results, save_vacancy_results, OVITO_AVAILABLE
    )
    OVITO_CORE_AVAILABLE = True
except ImportError:
    OVITO_CORE_AVAILABLE = False

__all__ = [
    'ElasticConstantsProcessor',
    'ThermomechanicalProcessor', 
    'load_elastic_constants_from_directory'
]

# Add OVITO exports if available
if OVITO_CORE_AVAILABLE:
    __all__.extend([
        'DislocationAnalysis',
        'WignerSeitzAnalysis', 
        'OvitoGPUConfig',
        'save_dislocation_results',
        'save_vacancy_results',
        'OVITO_AVAILABLE',
        'OVITO_CORE_AVAILABLE'
    ])
