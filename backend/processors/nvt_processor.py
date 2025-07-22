#!/usr/bin/env python3
"""
Processor classes for NVT ensemble simulation analysis
"""

from typing import Dict, Optional, List, Tuple
import pandas as pd

from ..core.thermomechanical import ThermomechanicalProcessor
from ..core.elastic_constants import ElasticConstantsProcessor


class NVTProcessor:
    """
    Processor for NVT (canonical) ensemble simulations
    """
    
    def __init__(self, sftp_config: Optional[Dict] = None):
        """
        Initialize NVT processor
        
        Args:
            sftp_config: SFTP configuration dictionary
        """
        self.thermo_processor = ThermomechanicalProcessor(sftp_config)
        self.elastic_processor = ElasticConstantsProcessor(sftp_config)
        self.ensemble_type = 'nvt'
        
    def process_simulation(self, simulation_file: str, 
                          elastic_constants_dir: Optional[str] = None,
                          elastic_files: Optional[List[str]] = None,
                          remote: bool = False,
                          compliance_params: Optional[Tuple[float, float, float]] = None) -> pd.DataFrame:
        """
        Complete NVT simulation processing pipeline
        
        Args:
            simulation_file: Path to simulation data file
            elastic_constants_dir: Directory containing elastic constant files
            elastic_files: List of elastic constant files (if remote)
            remote: Whether files are on remote server
            compliance_params: Tuple of (S11, S12, S44) if known
            
        Returns:
            DataFrame with complete analysis results
        """
        print("🔄 Starting NVT ensemble processing...")
        
        # Load simulation data
        print("📊 Loading simulation data...")
        data = self.thermo_processor.load_simulation_data(
            simulation_file, remote=remote, ensemble_type=self.ensemble_type
        )
        print(f"✅ Loaded {len(data)} data points")
        
        # Set compliance parameters
        if compliance_params:
            print("🔧 Using provided compliance parameters...")
            self.thermo_processor.set_compliance_parameters(*compliance_params)
        elif elastic_constants_dir:
            print("🔍 Calculating elastic constants...")
            if remote:
                from ..core.elastic_constants import load_elastic_constants_from_directory
                elastic_results = load_elastic_constants_from_directory(
                    elastic_constants_dir, 
                    file_list=elastic_files,
                    remote=remote,
                    sftp_config=None  # Will handle SFTP internally
                )
            else:
                import glob
                file_paths = glob.glob(f"{elastic_constants_dir}/*.txt") if elastic_constants_dir else []
                elastic_results = self.elastic_processor.process_complete_elastic_analysis(
                    file_paths, remote
                )
            
            params = elastic_results['compliance_parameters']
            self.thermo_processor.set_compliance_parameters(
                params['S11'], params['S12'], params['S44']
            )
            print(f"✅ Compliance parameters: S11={params['S11']:.2e}, S12={params['S12']:.2e}, S44={params['S44']:.2e}")
        else:
            raise ValueError("Either compliance_params or elastic_constants_dir must be provided")
        
        # Process thermomechanical analysis
        print("⚙️  Performing thermomechanical analysis...")
        results = self.thermo_processor.process_complete_analysis(data, self.ensemble_type)
        print(f"✅ Analysis complete - {len(results)} processed points")
        
        return results
    
    def analyze_and_save(self, simulation_file: str, output_file: str,
                        elastic_constants_dir: Optional[str] = None,
                        elastic_files: Optional[List[str]] = None,
                        remote: bool = False,
                        compliance_params: Optional[Tuple[float, float, float]] = None,
                        strain_threshold: float = 0.002) -> bool:
        """
        Complete analysis and save results
        
        Args:
            simulation_file: Path to simulation data file
            output_file: Path for output file
            elastic_constants_dir: Directory containing elastic constant files
            elastic_files: List of elastic constant files (if remote)
            remote: Whether files are on remote server
            compliance_params: Tuple of (S11, S12, S44) if known
            strain_threshold: Strain threshold for filtering analysis
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Process simulation
            results = self.process_simulation(
                simulation_file, elastic_constants_dir, elastic_files,
                remote, compliance_params
            )
            
            # Save results with filtered analysis
            success = self.thermo_processor.save_results(
                output_file, include_filtered=True, threshold=strain_threshold
            )
            
            if success:
                print(f"🎉 NVT analysis complete! Results saved to {output_file}")
                
                # Print summary statistics
                analysis = self.thermo_processor.filter_and_analyze(strain_threshold)
                print(f"\n📈 Summary Statistics (strain > {strain_threshold}):")
                for key, value in analysis['final_averages'].items():
                    print(f"   {key}: {value:.6f}")
            
            return success
            
        except Exception as e:
            print(f"❌ Error in NVT analysis: {str(e)}")
            return False
    
    def close_connections(self):
        """Close all connections"""
        self.thermo_processor.close_connections()
        self.elastic_processor.close_connections()


# Convenience function for standalone NVT processing
def process_nvt_simulation(simulation_file: str, 
                          output_file: str,
                          elastic_constants_dir: Optional[str] = None,
                          elastic_files: Optional[List[str]] = None,
                          remote: bool = False,
                          sftp_config: Optional[Dict] = None,
                          compliance_params: Optional[Tuple[float, float, float]] = None,
                          strain_threshold: float = 0.002) -> bool:
    """
    Standalone function to process NVT simulation
    
    Args:
        simulation_file: Path to simulation data file
        output_file: Path for output file
        elastic_constants_dir: Directory containing elastic constant files
        elastic_files: List of elastic constant files (if remote)
        remote: Whether files are on remote server
        sftp_config: SFTP configuration if remote
        compliance_params: Tuple of (S11, S12, S44) if known
        strain_threshold: Strain threshold for filtering analysis
        
    Returns:
        True if successful, False otherwise
    """
    processor = NVTProcessor(sftp_config)
    try:
        return processor.analyze_and_save(
            simulation_file, output_file, elastic_constants_dir,
            elastic_files, remote, compliance_params, strain_threshold
        )
    finally:
        processor.close_connections()
