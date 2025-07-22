#!/usr/bin/env python3
"""
OVITO Analysis Core Module - Simplified Version
Provides core functionality for OVITO-based analysis including DXA and WS
"""

import os
import sys
import tempfile
import glob
import fnmatch
from typing import List, Dict, Optional, Union, Tuple, Any
from tqdm import tqdm
import pandas as pd

# Handle OVITO imports safely
OVITO_AVAILABLE = False
try:
    import ovito
    from ovito.io import import_file, export_file
    from ovito.modifiers import (
        DislocationAnalysisModifier, 
        PolyhedralTemplateMatchingModifier, 
        SelectTypeModifier, 
        DeleteSelectedModifier, 
        WignerSeitzAnalysisModifier
    )
    from ovito.data import DislocationNetwork
    from ovito.pipeline import FileSource
    OVITO_AVAILABLE = True
except ImportError:
    OVITO_AVAILABLE = False
    print("⚠️  OVITO not available. Install with: pip install ovito")

# SFTP placeholder functions - will be replaced with real ones when SFTP is working
def download_file_sftp(remote_file, local_file, sftp_config):
    """Placeholder for SFTP download"""
    print(f"⚠️  SFTP download not available: {remote_file} -> {local_file}")
    return False

def list_remote_files(pattern, sftp_config):
    """Placeholder for SFTP file listing"""
    print(f"⚠️  SFTP file listing not available: {pattern}")
    return []


class OvitoGPUConfig:
    """GPU configuration for OVITO analysis"""
    
    @staticmethod
    def setup_gpu(gpu_id: int = 0, buffer_size: int = 4096) -> bool:
        """Configure GPU acceleration for OVITO"""
        os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
        os.environ['OVITO_GPU_ACCELERATION'] = '1'
        os.environ['OVITO_DEFAULT_DEVICE'] = 'cuda'
        os.environ['OVITO_GPU_BUFFER_SIZE'] = str(buffer_size)
        return OvitoGPUConfig.check_gpu_status()
    
    @staticmethod
    def check_gpu_status() -> bool:
        """Check GPU status and print configuration"""
        gpu_enabled = (os.environ.get('OVITO_GPU_ACCELERATION') == '1' and 
                      os.environ.get('CUDA_VISIBLE_DEVICES') not in [None, '', '-1'])
        
        print(f"🔧 Processing using: {'GPU' if gpu_enabled else 'CPU'}")
        if gpu_enabled:
            print("📊 GPU Configuration:")
            print(f"   - Device: {os.environ.get('OVITO_DEFAULT_DEVICE')}")
            print(f"   - Buffer Size: {os.environ.get('OVITO_GPU_BUFFER_SIZE')}MB")
            print(f"   - CUDA Device: {os.environ.get('CUDA_VISIBLE_DEVICES')}")
        else:
            print("💻 No GPU acceleration enabled")
        
        return gpu_enabled


class DislocationAnalysis:
    """Dislocation analysis using OVITO DXA"""
    
    def __init__(self, gpu_enabled: bool = True):
        """Initialize dislocation analysis"""
        if not OVITO_AVAILABLE:
            raise ImportError("OVITO is required for dislocation analysis")
        
        self.gpu_enabled = gpu_enabled
        if gpu_enabled:
            OvitoGPUConfig.setup_gpu()
    
    def analyze_dislocation_frame(self, input_file: str, reference_file: str, 
                                frame: int = 0) -> Dict[str, Any]:
        """Analyze dislocation in a single frame"""
        if not OVITO_AVAILABLE:
            return {
                'frame': frame,
                'error': 'OVITO not available',
                'total_length': 0.0,
                'segment_count': 0,
                'dislocation_density': 0.0,
                'volume': 0.0,
                'segments': []
            }
        
        try:
            # Use safe imports
            if 'import_file' in globals():
                pipeline = import_file(input_file)
            else:
                raise ImportError("OVITO import_file not available")
            
            # Use safe DXA modifier creation
            if 'DislocationAnalysisModifier' in globals():
                dxa = DislocationAnalysisModifier()
                
                # Try to set crystal structure if available
                try:
                    if hasattr(DislocationAnalysisModifier, 'Lattice'):
                        dxa.input_crystal_structure = DislocationAnalysisModifier.Lattice.FCC
                except:
                    pass
            else:
                raise ImportError("OVITO DislocationAnalysisModifier not available")
            
            pipeline.modifiers.append(dxa)
            
            # Compute the analysis
            data = pipeline.compute(frame)
            
            # Extract dislocation network safely
            dislocation_network = None
            if hasattr(data, 'dislocations'):
                dislocation_network = data.dislocations
            
            if dislocation_network and hasattr(dislocation_network, 'segments'):
                segments = dislocation_network.segments
                
                total_length = 0.0
                segment_count = len(segments)
                
                # Calculate total length safely
                for segment in segments:
                    if hasattr(segment, 'length'):
                        total_length += segment.length
                
                # Get cell volume safely
                volume = 0.0
                if hasattr(data, 'cell') and hasattr(data.cell, 'volume'):
                    volume = data.cell.volume
                
                results = {
                    'frame': frame,
                    'total_length': total_length,
                    'segment_count': segment_count,
                    'dislocation_density': total_length / volume if volume > 0 else 0.0,
                    'volume': volume,
                    'segments': []
                }
                
                # Extract segment details safely
                for i, segment in enumerate(segments):
                    segment_info = {
                        'id': i,
                        'length': getattr(segment, 'length', 0),
                        'burgers_vector': None,
                        'line_direction': None
                    }
                    
                    # Try to get Burgers vector
                    if hasattr(segment, 'true_burgers_vector'):
                        try:
                            segment_info['burgers_vector'] = list(segment.true_burgers_vector)
                        except:
                            pass
                    
                    results['segments'].append(segment_info)
                
                return results
            else:
                # No dislocations found
                volume = 0.0
                if hasattr(data, 'cell') and hasattr(data.cell, 'volume'):
                    volume = data.cell.volume
                
                return {
                    'frame': frame,
                    'total_length': 0.0,
                    'segment_count': 0,
                    'dislocation_density': 0.0,
                    'volume': volume,
                    'segments': []
                }
                
        except Exception as e:
            print(f"❌ Error analyzing frame {frame}: {e}")
            return {
                'frame': frame,
                'error': str(e),
                'total_length': 0.0,
                'segment_count': 0,
                'dislocation_density': 0.0,
                'volume': 0.0,
                'segments': []
            }
    
    def analyze_trajectory(self, input_pattern: str, reference_file: str,
                          frames: Optional[List[int]] = None,
                          remote: bool = False, sftp_config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Analyze dislocation evolution over multiple frames"""
        if not OVITO_AVAILABLE:
            return [{'frame': 0, 'error': 'OVITO not available', 'total_length': 0.0, 
                    'segment_count': 0, 'dislocation_density': 0.0, 'volume': 0.0, 'segments': []}]
        
        results = []
        
        # Skip remote file handling for now - not working
        if remote:
            print("⚠️  Remote file processing not available yet")
            return results
        
        try:
            # Handle local files only
            if os.path.isfile(input_pattern):
                # Single file with multiple frames
                try:
                    if 'import_file' in globals():
                        pipeline = import_file(input_pattern)
                        num_frames = getattr(pipeline.source, 'num_frames', 1)
                        
                        if frames is None:
                            frames = list(range(num_frames))
                        
                        for frame in tqdm(frames, desc="🔬 Analyzing frames"):
                            if frame < num_frames:
                                result = self.analyze_dislocation_frame(input_pattern, reference_file, frame)
                                results.append(result)
                except Exception as e:
                    print(f"❌ Error processing trajectory file: {e}")
            
            else:
                # Pattern matching for multiple files
                input_files = glob.glob(input_pattern)
                input_files.sort()
                
                if frames is None:
                    frames = list(range(len(input_files)))
                
                for i, frame in enumerate(tqdm(frames, desc="🔬 Analyzing frames")):
                    if i < len(input_files):
                        result = self.analyze_dislocation_frame(input_files[i], reference_file, 0)
                        result['frame'] = frame
                        result['source_file'] = input_files[i]
                        results.append(result)
            
            return results
            
        except Exception as e:
            print(f"❌ Error in trajectory analysis: {e}")
            return results


class WignerSeitzAnalysis:
    """Wigner-Seitz vacancy analysis using OVITO"""
    
    def __init__(self, gpu_enabled: bool = True):
        """Initialize Wigner-Seitz analysis"""
        if not OVITO_AVAILABLE:
            raise ImportError("OVITO is required for Wigner-Seitz analysis")
        
        self.gpu_enabled = gpu_enabled
        if gpu_enabled:
            OvitoGPUConfig.setup_gpu()
    
    def analyze_vacancies_frame(self, input_file: str, reference_file: str,
                               frame: int = 0) -> Dict[str, Any]:
        """Analyze vacancies in a single frame"""
        if not OVITO_AVAILABLE:
            return {
                'frame': frame,
                'error': 'OVITO not available',
                'total_sites': 0,
                'occupied_sites': 0,
                'vacant_sites': 0,
                'vacancy_concentration': 0.0,
                'volume': 0.0
            }
        
        try:
            # Use safe imports
            if 'import_file' in globals():
                pipeline = import_file(input_file)
            else:
                raise ImportError("OVITO import_file not available")
            
            # Add structure identification if available
            try:
                if 'PolyhedralTemplateMatchingModifier' in globals():
                    ptm = PolyhedralTemplateMatchingModifier()
                    pipeline.modifiers.append(ptm)
            except:
                pass
            
            # Add Wigner-Seitz analysis
            if 'WignerSeitzAnalysisModifier' in globals():
                ws = WignerSeitzAnalysisModifier()
                pipeline.modifiers.append(ws)
            else:
                raise ImportError("OVITO WignerSeitzAnalysisModifier not available")
            
            # Compute the analysis
            data = pipeline.compute(frame)
            
            # Extract vacancy information safely
            occupancy = None
            structure_types = None
            
            if hasattr(data, 'particles'):
                # Try different ways to access Occupancy
                try:
                    if hasattr(data.particles, 'Occupancy'):
                        occupancy = data.particles.Occupancy
                    elif 'Occupancy' in data.particles:
                        occupancy = data.particles['Occupancy']
                except:
                    pass
                
                # Try to get structure types
                try:
                    if hasattr(data.particles, 'Structure Type'):
                        structure_types = data.particles['Structure Type']
                    elif 'Structure Type' in data.particles:
                        structure_types = data.particles['Structure Type']
                except:
                    pass
            
            total_sites = len(occupancy) if occupancy is not None else 0
            vacant_sites = 0
            if occupancy is not None:
                try:
                    vacant_sites = sum(1 for occ in occupancy if occ == 0)
                except:
                    vacant_sites = 0
            
            occupied_sites = total_sites - vacant_sites
            
            # Get cell volume
            volume = 0.0
            if hasattr(data, 'cell') and hasattr(data.cell, 'volume'):
                volume = data.cell.volume
            
            results = {
                'frame': frame,
                'total_sites': total_sites,
                'occupied_sites': occupied_sites,
                'vacant_sites': vacant_sites,
                'vacancy_concentration': vacant_sites / total_sites if total_sites > 0 else 0.0,
                'volume': volume
            }
            
            # Add structure type information if available
            if structure_types is not None:
                structure_counts = {}
                try:
                    for st in structure_types:
                        structure_counts[st] = structure_counts.get(st, 0) + 1
                    results['structure_types'] = structure_counts
                except:
                    pass
            
            return results
            
        except Exception as e:
            print(f"❌ Error analyzing frame {frame}: {e}")
            return {
                'frame': frame,
                'error': str(e),
                'total_sites': 0,
                'occupied_sites': 0,
                'vacant_sites': 0,
                'vacancy_concentration': 0.0,
                'volume': 0.0
            }
    
    def analyze_vacancy_evolution(self, input_pattern: str, reference_file: str,
                                 frames: Optional[List[int]] = None,
                                 remote: bool = False, sftp_config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Analyze vacancy evolution over multiple frames"""
        if not OVITO_AVAILABLE:
            return [{'frame': 0, 'error': 'OVITO not available', 'total_sites': 0, 
                    'occupied_sites': 0, 'vacant_sites': 0, 'vacancy_concentration': 0.0, 'volume': 0.0}]
        
        results = []
        
        # Skip remote file handling for now
        if remote:
            print("⚠️  Remote file processing not available yet")
            return results
        
        try:
            # Handle local files only
            if os.path.isfile(input_pattern):
                # Single file with multiple frames
                try:
                    if 'import_file' in globals():
                        pipeline = import_file(input_pattern)
                        num_frames = getattr(pipeline.source, 'num_frames', 1)
                        
                        if frames is None:
                            frames = list(range(num_frames))
                        
                        for frame in tqdm(frames, desc="🔬 Analyzing vacancies"):
                            if frame < num_frames:
                                result = self.analyze_vacancies_frame(input_pattern, reference_file, frame)
                                results.append(result)
                except Exception as e:
                    print(f"❌ Error processing trajectory file: {e}")
            
            else:
                # Pattern matching for multiple files
                input_files = glob.glob(input_pattern)
                if not input_files:
                    # Try fnmatch for more complex patterns
                    base_dir = os.path.dirname(input_pattern) or '.'
                    pattern = os.path.basename(input_pattern)
                    try:
                        all_files = os.listdir(base_dir)
                        input_files = [os.path.join(base_dir, f) for f in all_files if fnmatch.fnmatch(f, pattern)]
                    except:
                        input_files = []
                
                input_files.sort()
                
                if frames is None:
                    frames = list(range(len(input_files)))
                
                for i, frame in enumerate(tqdm(frames, desc="🔬 Analyzing vacancies")):
                    if i < len(input_files):
                        result = self.analyze_vacancies_frame(input_files[i], reference_file, 0)
                        result['frame'] = frame
                        result['source_file'] = input_files[i]
                        results.append(result)
            
            return results
            
        except Exception as e:
            print(f"❌ Error in vacancy evolution analysis: {e}")
            return results


def save_dislocation_results(results: List[Dict[str, Any]], output_file: str) -> None:
    """Save dislocation analysis results to CSV file"""
    if not results:
        print("⚠️  No dislocation results to save")
        return
    
    # Prepare data for DataFrame
    data = []
    for result in results:
        row = {
            'frame': result.get('frame', 0),
            'total_length': result.get('total_length', 0.0),
            'segment_count': result.get('segment_count', 0),
            'dislocation_density': result.get('dislocation_density', 0.0),
            'volume': result.get('volume', 0.0),
            'source_file': result.get('source_file', ''),
            'error': result.get('error', '')
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"✅ Dislocation results saved to {output_file}")


def save_vacancy_results(results: List[Dict[str, Any]], output_file: str) -> None:
    """Save vacancy analysis results to CSV file"""
    if not results:
        print("⚠️  No vacancy results to save")
        return
    
    # Prepare data for DataFrame
    data = []
    for result in results:
        row = {
            'frame': result.get('frame', 0),
            'total_sites': result.get('total_sites', 0),
            'occupied_sites': result.get('occupied_sites', 0),
            'vacant_sites': result.get('vacant_sites', 0),
            'vacancy_concentration': result.get('vacancy_concentration', 0.0),
            'volume': result.get('volume', 0.0),
            'source_file': result.get('source_file', ''),
            'error': result.get('error', '')
        }
        
        # Add structure type counts if available
        if 'structure_types' in result:
            for struct_type, count in result['structure_types'].items():
                row[f'structure_type_{struct_type}'] = count
        
        data.append(row)
    
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"✅ Vacancy results saved to {output_file}")
