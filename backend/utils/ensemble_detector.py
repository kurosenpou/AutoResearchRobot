#!/usr/bin/env python3
"""
Ensemble Detection Utility
Automatically detects simulation ensemble type (NVE/NVT) based on data file format
"""

import os
import sys
from typing import Optional

def detect_simulation_ensemble(data_file: str, verbose: bool = False) -> str:
    """
    Detect simulation ensemble type based on data file format
    
    Args:
        data_file: Path to simulation data file
        verbose: Print detection details
        
    Returns:
        'nve' if no etally column found, 'nvt' if etally column present
    """
    if not os.path.exists(data_file):
        if verbose:
            print(f"❌ File not found: {data_file}")
        return 'nve'
    
    try:
        if verbose:
            print(f"🔍 Analyzing file: {data_file}")
        
        with open(data_file, 'r') as f:
            lines_checked = 0
            for line_num, line in enumerate(f, 1):
                if lines_checked > 20:  # Check more lines for better detection
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                lines_checked += 1
                
                # Check comment lines and header lines for etally
                if line.startswith('#') or any(keyword in line.lower() for keyword in ['step', 'time', 'temp', 'press']):
                    if 'etally' in line.lower():
                        if verbose:
                            print(f"✅ Found 'etally' in header/comment at line {line_num}")
                            print(f"🌡️ Detected: NVT ensemble")
                        return 'nvt'
                    continue
                
                # Check if etally appears anywhere in the line
                if 'etally' in line.lower():
                    if verbose:
                        print(f"✅ Found 'etally' at line {line_num}")
                        print(f"🌡️ Detected: NVT ensemble")
                    return 'nvt'
                
                # Try to parse as numerical data
                try:
                    values = line.split()
                    if len(values) > 5:  # Reasonable number of columns for simulation data
                        float_values = [float(val) for val in values]
                        if verbose:
                            print(f"📊 Found numerical data with {len(values)} columns at line {line_num}")
                        
                        # If we find numerical data without seeing etally, likely NVE
                        # But continue checking a few more lines
                        continue
                        
                except ValueError:
                    # Not numerical data, continue
                    continue
        
        if verbose:
            print("🔍 No 'etally' column detected")
            print("⚙️ Detected: NVE ensemble")
        
        return 'nve'
        
    except Exception as e:
        if verbose:
            print(f"❌ Error reading file: {e}")
            print("⚙️ Defaulting to: NVE ensemble")
        return 'nve'


def analyze_data_format(data_file: str) -> dict:
    """
    Analyze data file format and provide detailed information
    
    Args:
        data_file: Path to simulation data file
        
    Returns:
        Dictionary with format analysis results
    """
    analysis = {
        'ensemble_type': 'nve',
        'num_columns': 0,
        'has_header': False,
        'has_etally': False,
        'data_lines': 0,
        'comment_lines': 0,
        'file_size': 0
    }
    
    if not os.path.exists(data_file):
        return analysis
    
    analysis['file_size'] = os.path.getsize(data_file)
    
    try:
        with open(data_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if line_num > 100:  # Limit analysis to first 100 lines
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('#'):
                    analysis['comment_lines'] += 1
                    # Check comment lines for etally
                    if 'etally' in line.lower():
                        analysis['has_etally'] = True
                        analysis['ensemble_type'] = 'nvt'
                    continue
                
                # Check for etally in any line
                if 'etally' in line.lower():
                    analysis['has_etally'] = True
                    analysis['ensemble_type'] = 'nvt'
                
                # Check if this looks like a header
                if any(keyword in line.lower() for keyword in ['step', 'time', 'temp', 'press', 'vol']):
                    analysis['has_header'] = True
                    analysis['num_columns'] = len(line.split())
                    continue
                
                # Try to parse as numerical data
                try:
                    values = line.split()
                    float_values = [float(val) for val in values]
                    analysis['data_lines'] += 1
                    if analysis['num_columns'] == 0:
                        analysis['num_columns'] = len(values)
                except ValueError:
                    continue
    
    except Exception:
        pass
    
    return analysis


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect simulation ensemble type")
    parser.add_argument("data_file", help="Path to simulation data file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-a", "--analyze", action="store_true", help="Detailed format analysis")
    
    args = parser.parse_args()
    
    if args.analyze:
        print("📊 Data File Format Analysis")
        print("=" * 40)
        
        analysis = analyze_data_format(args.data_file)
        
        print(f"📁 File: {args.data_file}")
        print(f"📏 Size: {analysis['file_size']:,} bytes")
        print(f"🔬 Detected ensemble: {analysis['ensemble_type'].upper()}")
        print(f"📊 Number of columns: {analysis['num_columns']}")
        print(f"📋 Has header: {'Yes' if analysis['has_header'] else 'No'}")
        print(f"🧪 Has etally column: {'Yes' if analysis['has_etally'] else 'No'}")
        print(f"📈 Data lines: {analysis['data_lines']}")
        print(f"💬 Comment lines: {analysis['comment_lines']}")
        
        # Recommend processor
        if analysis['has_etally']:
            print("\n💡 Recommendation: Use NVT processor")
            print("   Command: python main.py nvt input.txt output.csv")
        else:
            print("\n💡 Recommendation: Use NVE processor")
            print("   Command: python main.py nve input.txt output.csv")
    
    else:
        ensemble = detect_simulation_ensemble(args.data_file, args.verbose)
        if not args.verbose:
            print(ensemble)
    
    sys.exit(0)
