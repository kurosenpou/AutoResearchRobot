#!/usr/bin/env python3
"""
Processors package for OVITO workflow backend
"""

from .nve_processor import NVEProcessor, process_nve_simulation
from .nvt_processor import NVTProcessor, process_nvt_simulation

# Auto-detection utilities
try:
    from ..utils.ensemble_detector import detect_simulation_ensemble
except ImportError:
    from backend.utils.ensemble_detector import detect_simulation_ensemble

def process_simulation_auto(simulation_file: str, output_file: str, **kwargs) -> bool:
    """
    Automatically detect ensemble type and process simulation data
    
    Args:
        simulation_file: Path to simulation data file
        output_file: Output file for results
        **kwargs: Additional arguments passed to the processor
        
    Returns:
        True if processing successful, False otherwise
    """
    ensemble_type = detect_simulation_ensemble(simulation_file, verbose=True)
    
    if ensemble_type == 'nvt':
        print("🌡️ Auto-detected NVT ensemble, using NVT processor...")
        return process_nvt_simulation(simulation_file, output_file, **kwargs)
    else:
        print("⚙️ Auto-detected NVE ensemble, using NVE processor...")
        return process_nve_simulation(simulation_file, output_file, **kwargs)

# OVITO analysis processors (optional imports - require OVITO)
OVITO_PROCESSORS_AVAILABLE = False
process_dxa_analysis = None
process_ws_analysis = None

try:
    from .dxa_processor import process_dxa_analysis
    from .ws_processor import process_ws_analysis
    OVITO_PROCESSORS_AVAILABLE = True
except ImportError:
    OVITO_PROCESSORS_AVAILABLE = False
    
    # Create fallback functions if OVITO is not available
    def _dxa_fallback(*args, **kwargs):
        print("❌ DXA analysis requires OVITO. Install with: pip install ovito")
        return False
    
    def _ws_fallback(*args, **kwargs):
        print("❌ WS analysis requires OVITO. Install with: pip install ovito")
        return False
    
    process_dxa_analysis = _dxa_fallback
    process_ws_analysis = _ws_fallback

__all__ = [
    'NVEProcessor',
    'NVTProcessor', 
    'process_nve_simulation',
    'process_nvt_simulation',
    'process_simulation_auto',
    'detect_simulation_ensemble',
    'process_dxa_analysis',
    'process_ws_analysis',
    'OVITO_PROCESSORS_AVAILABLE'
]
