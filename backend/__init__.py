#!/usr/bin/env python3
"""
OVITO Workflow Backend Package
Modular backend for thermomechanical analysis of LAMMPS simulation data
"""

from .processors import NVEProcessor, NVTProcessor, process_nve_simulation, process_nvt_simulation
from .core.elastic_constants import ElasticConstantsProcessor, load_elastic_constants_from_directory
from .core.thermomechanical import ThermomechanicalProcessor

__version__ = "1.0.0"
__author__ = "OVITO Workflow Team"
__description__ = "Modular backend for thermomechanical analysis"

__all__ = [
    'NVEProcessor',
    'NVTProcessor',
    'ElasticConstantsProcessor', 
    'ThermomechanicalProcessor',
    'process_nve_simulation',
    'process_nvt_simulation',
    'load_elastic_constants_from_directory'
]
