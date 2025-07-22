#!/usr/bin/env python3
"""
Main application interface for OVITO workflow backend
Provides command-line interface and convenience functions
"""

import argparse
import sys
import os
from typing import Dict, Optional

# Add backend to path for both standalone and module execution
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    # Try relative imports first (when run as module)
    from .processors import process_nve_simulation, process_nvt_simulation, process_simulation_auto, process_dxa_analysis, process_ws_analysis, OVITO_PROCESSORS_AVAILABLE
    from .processors.simulation_manager import run_complete_simulation_workflow
    from .utils.ensemble_detector import detect_simulation_ensemble, analyze_data_format
    from .core.elastic_constants import load_elastic_constants_from_directory
except ImportError:
    # Fall back to absolute imports (when run as script)
    try:
        from processors import process_nve_simulation, process_nvt_simulation, process_simulation_auto, process_dxa_analysis, process_ws_analysis, OVITO_PROCESSORS_AVAILABLE
        from processors.simulation_manager import run_complete_simulation_workflow
        from utils.ensemble_detector import detect_simulation_ensemble, analyze_data_format
        from core.elastic_constants import load_elastic_constants_from_directory
    except ImportError:
        # Last resort - try with backend prefix
        from backend.processors import process_nve_simulation, process_nvt_simulation, process_simulation_auto, process_dxa_analysis, process_ws_analysis, OVITO_PROCESSORS_AVAILABLE
        from backend.processors.simulation_manager import run_complete_simulation_workflow
        from backend.utils.ensemble_detector import detect_simulation_ensemble, analyze_data_format
        from backend.core.elastic_constants import load_elastic_constants_from_directory


def create_sftp_config_interactive() -> Dict:
    """
    Create SFTP configuration interactively
    
    Returns:
        SFTP configuration dictionary
    """
    print("🔐 SFTP Configuration Setup")
    print("Enter SFTP connection details:")
    
    hostname = input("Hostname: ")
    username = input("Username: ")
    
    return {
        'hostname': hostname,
        'username': username
    }


def process_elastic_constants_only(args):
    """Process elastic constants calculation only"""
    print("🔧 Processing elastic constants...")
    
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    try:
        results = load_elastic_constants_from_directory(
            args.elastic_dir,
            pattern="c*.txt",
            remote=args.remote,
            sftp_config=sftp_config,
            file_list=args.elastic_files.split(',') if args.elastic_files else None
        )
        
        print("\n✅ Elastic Constants Results:")
        print("=" * 40)
        for const, value in results['elastic_constants'].items():
            print(f"{const}: {value:.2e} Pa")
        
        print(f"\nCompliance Parameters:")
        params = results['compliance_parameters']
        print(f"S11: {params['S11']:.2e} Pa⁻¹")
        print(f"S12: {params['S12']:.2e} Pa⁻¹")
        print(f"S44: {params['S44']:.2e} Pa⁻¹")
        
        return True
        
    except Exception as e:
        print(f"❌ Error processing elastic constants: {e}")
        return False


def process_simulation_data(args):
    """Process simulation data (NVE or NVT)"""
    print(f"⚙️  Processing {args.ensemble.upper()} simulation...")
    
    # Set up SFTP if remote
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    # Set up compliance parameters or elastic constants
    compliance_params = None
    if args.compliance:
        try:
            values = [float(x.strip()) for x in args.compliance.split(',')]
            if len(values) != 3:
                raise ValueError("Need exactly 3 compliance values")
            compliance_params = (values[0], values[1], values[2])  # Explicit tuple creation
            print(f"🔧 Using compliance parameters: S11={values[0]:.2e}, S12={values[1]:.2e}, S44={values[2]:.2e}")
        except ValueError as e:
            print(f"❌ Error parsing compliance parameters: {e}")
            return False
    
    # Choose processor based on ensemble
    if args.ensemble.lower() == 'nve':
        success = process_nve_simulation(
            args.input_file,
            args.output_file,
            elastic_constants_dir=args.elastic_dir,
            elastic_files=args.elastic_files.split(',') if args.elastic_files else None,
            remote=args.remote,
            sftp_config=sftp_config,
            compliance_params=compliance_params,
            strain_threshold=args.threshold
        )
    elif args.ensemble.lower() == 'nvt':
        success = process_nvt_simulation(
            args.input_file,
            args.output_file,
            elastic_constants_dir=args.elastic_dir,
            elastic_files=args.elastic_files.split(',') if args.elastic_files else None,
            remote=args.remote,
            sftp_config=sftp_config,
            compliance_params=compliance_params,
            strain_threshold=args.threshold
        )
    else:
        print(f"❌ Unknown ensemble type: {args.ensemble}")
        return False
    
    return success


def process_dxa_command(args):
    """Process DXA analysis command"""
    if not OVITO_PROCESSORS_AVAILABLE:
        print("❌ DXA analysis requires OVITO. Install with: pip install ovito")
        return False
    
    print("🔬 Processing DXA (Dislocation Analysis)...")
    
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    return process_dxa_analysis(
        input_pattern=args.input_pattern,
        reference_file=args.reference_file,
        output_file=args.output_file,
        frames=args.frames,
        remote=args.remote,
        sftp_config=sftp_config,
        gpu_enabled=not args.no_gpu
    )


def process_ws_command(args):
    """Process WS vacancy analysis command"""
    if not OVITO_PROCESSORS_AVAILABLE:
        print("❌ WS analysis requires OVITO. Install with: pip install ovito")
        return False
    
    print("🔬 Processing WS (Wigner-Seitz Vacancy Analysis)...")
    
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    return process_ws_analysis(
        input_pattern=args.input_pattern,
        reference_file=args.reference_file,
        output_file=args.output_file,
        frames=args.frames,
        remote=args.remote,
        sftp_config=sftp_config,
        gpu_enabled=not args.no_gpu
    )


def process_simulation_workflow_command(args):
    """Process complete simulation workflow command"""
    print("🎯 Processing Complete Simulation Workflow...")
    
    # Get SFTP configuration
    if hasattr(args, 'config') and args.config and os.path.exists(args.config):
        import json
        with open(args.config, 'r') as f:
            sftp_config = json.load(f)
    else:
        sftp_config = create_sftp_config_interactive()
    
    return run_complete_simulation_workflow(
        local_path=args.local_path,
        remote_path=args.remote_path,
        nve_output=args.nve_output,
        ws_output=args.ws_output,
        dxa_output=args.dxa_output,
        sftp_config=sftp_config
    )


def process_auto_command(args):
    """Process automatic ensemble detection and analysis"""
    print("🔍 Auto-detecting simulation ensemble type...")
    
    # First analyze the file format
    analysis = analyze_data_format(args.input_file)
    
    print(f"📊 File Analysis Results:")
    print(f"  📁 File: {args.input_file}")
    print(f"  📏 Size: {analysis['file_size']:,} bytes")
    print(f"  📊 Columns: {analysis['num_columns']}")
    print(f"  📋 Has header: {'Yes' if analysis['has_header'] else 'No'}")
    print(f"  🧪 Has etally: {'Yes' if analysis['has_etally'] else 'No'}")
    print(f"  📈 Data lines: {analysis['data_lines']}")
    print(f"  💬 Comment lines: {analysis['comment_lines']}")
    
    ensemble_type = analysis['ensemble_type']
    print(f"\n🔬 Detected ensemble: {ensemble_type.upper()}")
    
    if ensemble_type == 'nvt':
        print("🌡️ Using NVT processor...")
    else:
        print("⚙️ Using NVE processor...")
    
    # Get SFTP configuration if needed
    sftp_config = None
    if args.remote:
        sftp_config = create_sftp_config_interactive()
    
    # Process with auto-detection
    success = process_simulation_auto(
        simulation_file=args.input_file,
        output_file=args.output_file,
        elastic_constants_dir=args.elastic_dir,
        elastic_files=args.elastic_files.split(',') if args.elastic_files else None,
        remote=args.remote,
        sftp_config=sftp_config,
        compliance_params=None,  # Could add compliance parsing here if needed
        strain_threshold=getattr(args, 'threshold', 0.001)
    )
    
    if success:
        print(f"\n✅ {ensemble_type.upper()} analysis completed successfully!")
    else:
        print(f"\n❌ {ensemble_type.upper()} analysis failed!")
    
    return success


def main():
    """Main command-line interface"""
    parser = argparse.ArgumentParser(
        description="OVITO Workflow Backend - Thermomechanical Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
📋 DETAILED USAGE EXAMPLES:

🔧 Elastic Constants Analysis:
  # Local files (requires c1144.txt, c2255.txt, c3366.txt, etc.)
  python main.py elastic ./elastic_data/
  
  # Remote SFTP files with specific file list
  python main.py elastic user@server:/path/to/elastic/ --remote --elastic-files "c1144.txt,c2255.txt,c3366.txt"

⚙️  NVE Simulation Processing:
  # Local files with elastic constants calculation
  python main.py nve simulation.txt results.csv --elastic-dir ./elastic_data/ --threshold 0.001
  
  # Remote simulation with known compliance parameters
  python main.py nve user@server:/sim.txt output.csv --remote --compliance "1e-11,-2e-12,3e-11"
  
  # High-precision analysis with custom threshold
  python main.py nve simulation.txt results.csv --elastic-dir ./elastic/ --threshold 0.0005

🌡️  NVT Simulation Processing:
  # Local NVT ensemble with elastic constants
  python main.py nvt nvt_simulation.txt nvt_results.csv --elastic-dir ./elastic_data/
  
  # Remote NVT with pre-calculated compliance
  python main.py nvt user@server:/nvt.txt output.csv --remote --compliance "1.2e-11,-1.8e-12,2.9e-11"

🤖 Auto-Detection Processing:
  # Automatically detect ensemble type (NVE/NVT) and process accordingly
  python main.py auto simulation.txt results.csv --elastic-dir ./elastic_data/
  
  # Remote auto-detection with threshold adjustment
  python main.py auto user@server:/data.txt output.csv --remote --threshold 0.0005
  
  # Auto-detection analyzes file format and uses appropriate processor:
  # - Files with 'etally' column → NVT processor
  # - Files without 'etally' column → NVE processor

🔬 DXA Dislocation Analysis (requires OVITO):
  # Local trajectory analysis
  python main.py dxa "trajectory*.dump" reference.dump dislocation_results.csv
  
  # Remote analysis with specific frames
  python main.py dxa user@server:/path/traj* reference.dump results.csv --remote --frames 0 100 200

🧪 WS Vacancy Analysis (requires OVITO):
  # Local trajectory with reference structure
  python main.py ws "trajectory*.dump" reference.structure vacancy_results.csv
  
  # Remote analysis with GPU acceleration disabled
  python main.py ws user@server:/path/traj* ref.dump results.csv --remote --no-gpu

🎯 Complete Simulation Workflow:
  # Upload files, run simulation, monitor, and analyze automatically
  python main.py simulate ./input_files/ /remote/simulation/path/ nve_results.csv ws_results.csv dxa_results.csv
  
  # With SFTP configuration file
  python main.py simulate ./local_files/ /hpc/user/sim001/ nve.csv ws.csv dxa.csv --config sftp_config.json
  
  Required input files: *.lmp, in.*.lammps, run.*.sh, dbg.*.sh
  Monitors for restart.relax completion, then runs analyses on *d2-*.txt and shear/3.dump.shear-II.* files
  # GPU-accelerated processing
  python main.py dxa trajectory.dump reference.dump results.csv

🧩 WS Vacancy Analysis (requires OVITO):
  # Local vacancy evolution analysis
  python main.py ws "simulation*.dump" perfect_crystal.dump vacancy_results.csv
  
  # Remote analysis with frame selection
  python main.py ws user@server:/path/sim* reference.dump vacancies.csv --remote --frames 0 50 100
  
  # CPU-only processing
  python main.py ws trajectory.dump reference.dump results.csv --no-gpu

�📊 File Format Requirements:
  Simulation Data: step, l_1, l_2, l_3, l_4, l_5, l_6, p_1, p_2, p_3, p_4, p_5, p_6, vol, ep, ek, u, t, rho, entropy[, etally]
  Elastic Data: delta_exx, delta_eyy, delta_ezz, delta_exy, delta_eyz, delta_exz, delta_pxx, delta_pyy, delta_pzz, delta_pxy, delta_pyz, delta_pxz
  OVITO Files: LAMMPS dump files, XYZ, CFG, or any format supported by OVITO

🔐 Remote Access:
  SFTP URL format: user@hostname:/path/to/file
  Supports interactive authentication with OTP/2FA
  Automatic file download and cleanup

🎯 Analysis Features:
  - Elastic constants calculation with linear regression
  - Elastic-plastic strain decomposition
  - Von Mises equivalent stress/strain
  - Taylor-Quinney coefficient (TQC) analysis
  - Work and energy balance computations
  - Statistical filtering and averaging
  - Dislocation density and evolution tracking (DXA)
  - Vacancy concentration and structural analysis (WS)
  - GPU-accelerated OVITO processing
        """
    )
    
    parser.add_argument(
        '--version', 
        action='version', 
        version='OVITO Workflow Backend v1.0.0 - Thermomechanical Analysis Tool'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available analysis commands')
    
    # Elastic constants command
    elastic_parser = subparsers.add_parser(
        'elastic', 
        help='Calculate elastic constants from stress-strain data',
        description='Calculate elastic constants using linear regression analysis of stress-strain relationships'
    )
    elastic_parser.add_argument(
        'elastic_dir', 
        help='Directory containing elastic constant files (c1144.txt, c2255.txt, c3366.txt, etc.)'
    )
    elastic_parser.add_argument(
        '--elastic-files', 
        help='Comma-separated list of specific elastic constant files to process'
    )
    elastic_parser.add_argument(
        '--remote', 
        action='store_true', 
        help='Files are located on remote SFTP server (requires interactive authentication)'
    )
    
    # NVE simulation command
    nve_parser = subparsers.add_parser(
        'nve', 
        help='Process NVE (microcanonical) ensemble simulation data',
        description='Complete thermomechanical analysis for NVE ensemble simulations including elastic-plastic decomposition and TQC analysis'
    )
    nve_parser.add_argument('input_file', help='Input simulation data file path (local or remote SFTP)')
    nve_parser.add_argument('output_file', help='Output results file path (CSV format)')
    nve_parser.add_argument(
        '--elastic-dir', 
        help='Directory containing elastic constant files for compliance matrix calculation'
    )
    nve_parser.add_argument(
        '--elastic-files', 
        help='Comma-separated list of elastic constant files (if different from default)'
    )
    nve_parser.add_argument(
        '--compliance', 
        help='Pre-calculated compliance parameters as "S11,S12,S44" (Pa⁻¹) - skip elastic constants calculation'
    )
    nve_parser.add_argument(
        '--remote', 
        action='store_true', 
        help='Input files are on remote SFTP server'
    )
    nve_parser.add_argument(
        '--threshold', 
        type=float, 
        default=0.002, 
        help='Strain threshold for statistical analysis filtering (default: 0.002)'
    )
    
    # NVT simulation command
    nvt_parser = subparsers.add_parser(
        'nvt', 
        help='Process NVT (canonical) ensemble simulation data',
        description='Complete thermomechanical analysis for NVT ensemble simulations with temperature control effects'
    )
    nvt_parser.add_argument('input_file', help='Input simulation data file path (local or remote SFTP)')
    nvt_parser.add_argument('output_file', help='Output results file path (CSV format)')
    nvt_parser.add_argument(
        '--elastic-dir', 
        help='Directory containing elastic constant files for compliance matrix calculation'
    )
    nvt_parser.add_argument(
        '--elastic-files', 
        help='Comma-separated list of elastic constant files (if different from default)'
    )
    nvt_parser.add_argument(
        '--compliance', 
        help='Pre-calculated compliance parameters as "S11,S12,S44" (Pa⁻¹) - skip elastic constants calculation'
    )
    nvt_parser.add_argument(
        '--remote', 
        action='store_true', 
        help='Input files are on remote SFTP server'
    )
    nvt_parser.add_argument(
        '--threshold', 
        type=float, 
        default=0.002, 
        help='Strain threshold for statistical analysis filtering (default: 0.002)'
    )
    
    # Auto-detection command
    auto_parser = subparsers.add_parser(
        'auto',
        help='Automatically detect ensemble type (NVE/NVT) and process simulation data',
        description='Automatically detect simulation ensemble type based on data format and run appropriate analysis'
    )
    auto_parser.add_argument('input_file', help='Input simulation data file')
    auto_parser.add_argument('output_file', help='Output CSV file for analysis results')
    auto_parser.add_argument(
        '--elastic-dir', 
        help='Directory containing elastic constants files (c1144.txt, c2255.txt, etc.)'
    )
    auto_parser.add_argument(
        '--elastic-files', 
        help='Comma-separated list of elastic constants files (for remote access)'
    )
    auto_parser.add_argument(
        '--remote', 
        action='store_true', 
        help='Input files are on remote SFTP server'
    )
    auto_parser.add_argument(
        '--threshold', 
        type=float, 
        default=0.001, 
        help='Strain threshold for statistical analysis filtering (default: 0.001)'
    )
    
    # DXA analysis command
    if OVITO_PROCESSORS_AVAILABLE:
        dxa_parser = subparsers.add_parser(
            'dxa',
            help='Perform DXA (Dislocation Analysis) using OVITO',
            description='Analyze dislocation evolution in molecular dynamics simulations using OVITO DXA'
        )
        dxa_parser.add_argument('input_pattern', help='Input file pattern (local files or remote SFTP URL pattern)')
        dxa_parser.add_argument('reference_file', help='Reference structure file for DXA')
        dxa_parser.add_argument('output_file', help='Output CSV file for dislocation analysis results')
        dxa_parser.add_argument(
            '--frames', 
            nargs='+', 
            type=int, 
            help='Specific frame numbers to analyze (default: all frames)'
        )
        dxa_parser.add_argument(
            '--remote', 
            action='store_true', 
            help='Input files are on remote SFTP server'
        )
        dxa_parser.add_argument(
            '--no-gpu', 
            action='store_true', 
            help='Disable GPU acceleration for OVITO processing'
        )
    
    # WS vacancy analysis command
    if OVITO_PROCESSORS_AVAILABLE:
        ws_parser = subparsers.add_parser(
            'ws',
            help='Perform WS (Wigner-Seitz) vacancy analysis using OVITO',
            description='Analyze vacancy evolution in molecular dynamics simulations using OVITO Wigner-Seitz analysis'
        )
        ws_parser.add_argument('input_pattern', help='Input file pattern (local files or remote SFTP URL pattern)')
        ws_parser.add_argument('reference_file', help='Reference structure file for WS analysis')
        ws_parser.add_argument('output_file', help='Output CSV file for vacancy analysis results')
        ws_parser.add_argument(
            '--frames', 
            nargs='+', 
            type=int, 
            help='Specific frame numbers to analyze (default: all frames)'
        )
        ws_parser.add_argument(
            '--remote', 
            action='store_true', 
            help='Input files are on remote SFTP server'
        )
        ws_parser.add_argument(
            '--no-gpu', 
            action='store_true', 
            help='Disable GPU acceleration for OVITO processing'
        )
    
    # Complete simulation workflow command
    sim_parser = subparsers.add_parser(
        'simulate',
        help='Complete simulation workflow: upload, run, monitor, and analyze',
        description='Complete MD simulation workflow from local files to remote HPC server with automatic analysis'
    )
    sim_parser.add_argument('local_path', help='Local directory containing input files (*.lmp, in.*.lammps, run.*.sh, dbg.*.sh)')
    sim_parser.add_argument('remote_path', help='Remote directory to upload files to and run simulation')
    sim_parser.add_argument('nve_output', help='Output file for NVE/NVT analysis results')
    sim_parser.add_argument('ws_output', help='Output file for Wigner-Seitz vacancy analysis results')
    sim_parser.add_argument('dxa_output', help='Output file for DXA dislocation analysis results')
    sim_parser.add_argument(
        '--config', 
        help='SFTP configuration file (JSON format with hostname, username, etc.)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    print("🚀 OVITO Workflow Backend")
    print("=" * 50)
    
    # Execute command
    try:
        if args.command == 'elastic':
            success = process_elastic_constants_only(args)
        elif args.command in ['nve', 'nvt']:
            args.ensemble = args.command
            success = process_simulation_data(args)
        elif args.command == 'auto':
            success = process_auto_command(args)
        elif args.command == 'dxa':
            success = process_dxa_command(args)
        elif args.command == 'ws':
            success = process_ws_command(args)
        elif args.command == 'simulate':
            success = process_simulation_workflow_command(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            success = False
        
        if success:
            print("\n🎉 Operation completed successfully!")
            return 0
        else:
            print("\n❌ Operation failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
