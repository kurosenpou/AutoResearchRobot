#!/usr/bin/env python3
"""
DXA (Dislocation Analysis) Processor
Provides high-level interface for dislocation analysis using OVITO
"""

import os
import sys
from typing import List, Optional, Dict
import pandas as pd

# Add parent directory for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from ..core.ovito_analysis import DislocationAnalysis, save_dislocation_results, OVITO_AVAILABLE
    from ..utils.sftp_utils import SFTPManager
except ImportError:
    try:
        from core.ovito_analysis import DislocationAnalysis, save_dislocation_results, OVITO_AVAILABLE
        from utils.sftp_utils import SFTPManager
    except ImportError:
        from backend.core.ovito_analysis import DislocationAnalysis, save_dislocation_results, OVITO_AVAILABLE
        from backend.utils.sftp_utils import SFTPManager


def process_dxa_analysis(input_pattern: str, reference_file: str, output_file: str,
                        frames: Optional[List[int]] = None, remote: bool = False,
                        sftp_config: Optional[Dict] = None, gpu_enabled: bool = True) -> bool:
    """
    Process dislocation analysis on simulation data
    
    Args:
        input_pattern: Pattern for input simulation files
        reference_file: Reference structure file for DXA
        output_file: Output CSV file for results
        frames: List of frame numbers to analyze (None for all)
        remote: Whether files are on remote server
        sftp_config: SFTP configuration if remote=True
        gpu_enabled: Enable GPU acceleration
        
    Returns:
        True if processing successful, False otherwise
    """
    
    if not OVITO_AVAILABLE:
        print("❌ OVITO is not available. Please install with: pip install ovito")
        return False
    
    print("🔬 Starting DXA (Dislocation Analysis)")
    print("=" * 50)
    
    if remote:
        print(f"📡 Remote analysis: {input_pattern}")
        if not sftp_config:
            print("❌ SFTP configuration required for remote analysis")
            return False
    else:
        print(f"📁 Local analysis: {input_pattern}")
    
    print(f"📊 Reference file: {reference_file}")
    print(f"🎯 Output file: {output_file}")
    
    if frames:
        print(f"🔢 Analyzing frames: {frames[:5]}{'...' if len(frames) > 5 else ''} ({len(frames)} total)")
    else:
        print("🔢 Analyzing all available frames")
    
    try:
        # Initialize DXA analysis
        dxa_analyzer = DislocationAnalysis(gpu_enabled=gpu_enabled)
        
        # Perform analysis
        print("\n🔄 Running dislocation analysis...")
        results = dxa_analyzer.analyze_trajectory(
            input_pattern=input_pattern,
            reference_file=reference_file,
            frames=frames,
            remote=remote,
            sftp_config=sftp_config
        )
        
        if not results:
            print("❌ No results obtained from analysis")
            return False
        
        # Save results
        print(f"\n💾 Saving results to {output_file}...")
        save_dislocation_results(results, output_file)
        
        # Generate summary
        summary_file = output_file.replace('.csv', '_summary.txt')
        generate_dxa_summary(results, summary_file)
        
        print("\n✅ DXA analysis completed successfully!")
        print(f"📊 Analyzed {len(results)} frames")
        print(f"📄 Results: {output_file}")
        print(f"📋 Summary: {summary_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in DXA analysis: {e}")
        return False


def generate_dxa_summary(results: List[Dict], summary_file: str) -> None:
    """
    Generate summary statistics for DXA analysis
    
    Args:
        results: List of analysis results
        summary_file: Output summary file path
    """
    if not results:
        return
    
    # Calculate statistics
    valid_results = [r for r in results if 'error' not in r or not r['error']]
    
    if not valid_results:
        with open(summary_file, 'w') as f:
            f.write("DXA Analysis Summary\n")
            f.write("=" * 40 + "\n\n")
            f.write("No valid results obtained.\n")
        return
    
    total_lengths = [r['total_length'] for r in valid_results]
    segment_counts = [r['segment_count'] for r in valid_results]
    densities = [r['dislocation_density'] for r in valid_results]
    volumes = [r['volume'] for r in valid_results if r['volume'] > 0]
    
    with open(summary_file, 'w') as f:
        f.write("DXA (Dislocation Analysis) Summary\n")
        f.write("=" * 40 + "\n\n")
        
        f.write(f"Total frames analyzed: {len(results)}\n")
        f.write(f"Valid results: {len(valid_results)}\n")
        f.write(f"Failed analyses: {len(results) - len(valid_results)}\n\n")
        
        if total_lengths:
            f.write("Dislocation Length Statistics:\n")
            f.write(f"  Average total length: {sum(total_lengths)/len(total_lengths):.2e} Å\n")
            f.write(f"  Maximum total length: {max(total_lengths):.2e} Å\n")
            f.write(f"  Minimum total length: {min(total_lengths):.2e} Å\n\n")
        
        if segment_counts:
            f.write("Segment Count Statistics:\n")
            f.write(f"  Average segments: {sum(segment_counts)/len(segment_counts):.1f}\n")
            f.write(f"  Maximum segments: {max(segment_counts)}\n")
            f.write(f"  Minimum segments: {min(segment_counts)}\n\n")
        
        if densities:
            f.write("Dislocation Density Statistics:\n")
            f.write(f"  Average density: {sum(densities)/len(densities):.2e} Å⁻²\n")
            f.write(f"  Maximum density: {max(densities):.2e} Å⁻²\n")
            f.write(f"  Minimum density: {min(densities):.2e} Å⁻²\n\n")
        
        if volumes:
            f.write("System Volume Statistics:\n")
            f.write(f"  Average volume: {sum(volumes)/len(volumes):.2e} Å³\n")
            f.write(f"  Volume range: {min(volumes):.2e} - {max(volumes):.2e} Å³\n\n")
        
        # Frame-by-frame summary
        f.write("Frame-by-Frame Results:\n")
        f.write("-" * 30 + "\n")
        f.write("Frame\tLength (Å)\tSegments\tDensity (Å⁻²)\n")
        
        for result in valid_results[:20]:  # Limit to first 20 frames
            frame = result.get('frame', 0)
            length = result.get('total_length', 0.0)
            segments = result.get('segment_count', 0)
            density = result.get('dislocation_density', 0.0)
            f.write(f"{frame}\t{length:.2e}\t{segments}\t{density:.2e}\n")
        
        if len(valid_results) > 20:
            f.write(f"... and {len(valid_results) - 20} more frames\n")


def create_sftp_config_interactive() -> Dict:
    """
    Create SFTP configuration interactively for DXA
    
    Returns:
        SFTP configuration dictionary
    """
    print("🔐 SFTP Configuration for DXA Analysis")
    print("Enter connection details:")
    
    hostname = input("Hostname: ").strip()
    username = input("Username: ").strip()
    
    return {
        'hostname': hostname,
        'username': username
    }


# Backward compatibility function
def run_dxa_analysis(input_pattern: str, reference_file: str, output_file: str,
                    frames: Optional[List[int]] = None, remote_config: Optional[Dict] = None) -> bool:
    """
    Backward compatibility function for DXA analysis
    
    Args:
        input_pattern: Pattern for input files
        reference_file: Reference structure file
        output_file: Output CSV file
        frames: Frame numbers to analyze
        remote_config: Remote configuration if needed
        
    Returns:
        True if successful, False otherwise
    """
    return process_dxa_analysis(
        input_pattern=input_pattern,
        reference_file=reference_file,
        output_file=output_file,
        frames=frames,
        remote=bool(remote_config),
        sftp_config=remote_config
    )


if __name__ == "__main__":
    # Command line interface for standalone usage
    import argparse
    
    parser = argparse.ArgumentParser(description="DXA Dislocation Analysis")
    parser.add_argument("input_pattern", help="Input file pattern")
    parser.add_argument("reference_file", help="Reference structure file")
    parser.add_argument("output_file", help="Output CSV file")
    parser.add_argument("--frames", nargs="+", type=int, help="Frame numbers to analyze")
    parser.add_argument("--remote", action="store_true", help="Files are on remote server")
    parser.add_argument("--no-gpu", action="store_true", help="Disable GPU acceleration")
    
    args = parser.parse_args()
    
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    success = process_dxa_analysis(
        input_pattern=args.input_pattern,
        reference_file=args.reference_file,
        output_file=args.output_file,
        frames=args.frames,
        remote=args.remote,
        sftp_config=sftp_config,
        gpu_enabled=not args.no_gpu
    )
    
    sys.exit(0 if success else 1)
