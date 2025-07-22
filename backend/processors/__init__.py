#!/usr/bin/env python3
"""
Processors package for OVITO workflow backend
"""

from .nve_processor import NVEProcessor, process_nve_simulation
from .nvt_processor import NVTProcessor, process_nvt_simulation

# OVITO analysis processors (optional imports - require OVITO)
try:
    from .dxa_processor import process_dxa_analysis
    from .ws_processor import process_ws_analysis
    OVITO_PROCESSORS_AVAILABLE = True
except ImportError:
    OVITO_PROCESSORS_AVAILABLE = False
    def process_dxa_analysis(*args, **kwargs):
        print("❌ DXA analysis requires OVITO. Install with: pip install ovito")
        return False
    def process_ws_analysis(*args, **kwargs):
        print("❌ WS analysis requires OVITO. Install with: pip install ovito")
        return False

__all__ = [
    'NVEProcessor',
    'NVTProcessor', 
    'process_nve_simulation',
    'process_nvt_simulation',
    'process_dxa_analysis',
    'process_ws_analysis',
    'OVITO_PROCESSORS_AVAILABLE'
]
