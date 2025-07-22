#!/usr/bin/env python3
"""
Core module for thermomechanical analysis
Provides functionality for NVE and NVT ensemble simulation post-processing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import os
import tempfile

from ..utils.sftp_utils import SFTPManager
from ..utils.file_utils import read_data_file, write_output_file
from ..utils.math_utils import (
    calculate_logarithmic_strain, calculate_engineering_strain,
    calculate_von_mises_strain, calculate_von_mises_stress,
    calculate_elastic_strain, calculate_plastic_strain,
    calculate_work_terms, calculate_cumulative_sum,
    calculate_beta_parameters, calculate_beta_parameters_nve,
    filter_data_by_threshold, calculate_averages_above_threshold
)
from ..config.constants import NVE_DATA_HEADERS, NVT_DATA_HEADERS, EV_TO_J, ANGSTROM3_TO_M3


class ThermomechanicalProcessor:
    """
    Base processor for thermomechanical analysis
    """
    
    def __init__(self, sftp_config: Optional[Dict] = None):
        """
        Initialize thermomechanical processor
        
        Args:
            sftp_config: SFTP configuration dictionary
        """
        self.sftp_manager = SFTPManager() if sftp_config else None
        self.data = None
        self.processed_data = None
        self.compliance_parameters = None
        
    def load_simulation_data(self, file_path: str, remote: bool = False, 
                           ensemble_type: str = 'nve') -> pd.DataFrame:
        """
        Load simulation data from file
        
        Args:
            file_path: Path to the simulation data file
            remote: Whether to load from remote server
            ensemble_type: Type of ensemble ('nve' or 'nvt')
            
        Returns:
            DataFrame with simulation data
        """
        # Choose appropriate headers based on ensemble type
        headers = NVT_DATA_HEADERS if ensemble_type.lower() == 'nvt' else NVE_DATA_HEADERS
        
        if remote and self.sftp_manager:
            # Download and process remote file
            username, hostname, remote_path = self.sftp_manager.parse_sftp_url(file_path)
            if self.sftp_manager.authenticate(hostname, username):
                with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
                    temp_path = temp_file.name
                self.sftp_manager.download_file(remote_path, temp_path)
                data = read_data_file(temp_path, headers)
                os.unlink(temp_path)  # Clean up temp file
                self.sftp_manager.close()
                return data
            else:
                raise Exception("Failed to authenticate to remote server")
        else:
            return read_data_file(file_path, headers)
    
    def set_compliance_parameters(self, S11: float, S12: float, S44: float):
        """
        Set compliance matrix parameters
        
        Args:
            S11: S11 compliance parameter
            S12: S12 compliance parameter  
            S44: S44 compliance parameter
        """
        self.compliance_parameters = (S11, S12, S44)
    
    def calculate_strain_components(self, data: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Calculate strain components from simulation data
        
        Args:
            data: DataFrame with simulation data
            
        Returns:
            Dictionary with strain components
        """
        strains = {}
        
        # Logarithmic strains for normal components (using proper column names)
        strains['e1'] = calculate_logarithmic_strain(np.array(data['l_1'].values))
        strains['e2'] = calculate_logarithmic_strain(np.array(data['l_2'].values))
        strains['e3'] = calculate_logarithmic_strain(np.array(data['l_3'].values))
        
        # Engineering strains for shear components
        strains['e4'] = calculate_engineering_strain(np.array(data['l_4'].values))
        strains['e5'] = calculate_engineering_strain(np.array(data['l_5'].values))
        strains['e6'] = calculate_engineering_strain(np.array(data['l_6'].values))
        
        return strains
    
    def calculate_stress_components(self, data: pd.DataFrame, volume: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Calculate stress components from simulation data
        
        Args:
            data: DataFrame with simulation data
            volume: Array of volume values
            
        Returns:
            Dictionary with stress components
        """
        stresses = {}
        
        # Convert pressure from atm to Pa and calculate stress components
        # Note: LAMMPS outputs pressure, stress = -pressure
        conversion_factor = -101325  # atm to Pa conversion with sign flip
        
        stresses['s1'] = np.array(data['p_1'].values) * conversion_factor
        stresses['s2'] = np.array(data['p_2'].values) * conversion_factor
        stresses['s3'] = np.array(data['p_3'].values) * conversion_factor
        stresses['s4'] = np.array(data['p_4'].values) * conversion_factor
        stresses['s5'] = np.array(data['p_5'].values) * conversion_factor
        stresses['s6'] = np.array(data['p_6'].values) * conversion_factor
        
        return stresses
    
    def calculate_stress_rates(self, stresses: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Calculate stress rate components
        
        Args:
            stresses: Dictionary with stress components
            
        Returns:
            Dictionary with stress rate components
        """
        stress_rates = {}
        
        for key, stress_array in stresses.items():
            # Calculate differences (rates)
            rate = np.concatenate([[0], np.diff(stress_array)])
            stress_rates[f'd{key}'] = rate
            
        return stress_rates
    
    def calculate_volume_and_derivatives(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate volume and its time derivative
        
        Args:
            data: DataFrame with simulation data
            
        Returns:
            Tuple of (volume, volume_rate)
        """
        volume = np.array(data['vol'].values)
        volume_rate = np.concatenate([[0], np.diff(volume)])
        
        return volume, volume_rate
    
    def calculate_elastic_plastic_decomposition(self, strains: Dict[str, np.ndarray], 
                                              stress_rates: Dict[str, np.ndarray]) -> Tuple[Dict, Dict]:
        """
        Calculate elastic and plastic strain decomposition
        
        Args:
            strains: Dictionary with total strain components
            stress_rates: Dictionary with stress rate components
            
        Returns:
            Tuple of (elastic_strains, plastic_strains) dictionaries
        """
        if self.compliance_parameters is None:
            raise ValueError("Compliance parameters not set. Call set_compliance_parameters first.")
        
        # Calculate elastic strain increments
        stress_rate_list = [
            stress_rates['ds1'], stress_rates['ds2'], stress_rates['ds3'],
            stress_rates['ds4'], stress_rates['ds5'], stress_rates['ds6']
        ]
        
        elastic_strain_increments = calculate_elastic_strain(stress_rate_list, self.compliance_parameters)
        
        # Calculate cumulative elastic strains
        elastic_strains = {}
        for i, key in enumerate(['e1', 'e2', 'e3', 'e4', 'e5', 'e6']):
            elastic_strains[key] = calculate_cumulative_sum(elastic_strain_increments[i])
        
        # Calculate plastic strains
        total_strain_list = [strains['e1'], strains['e2'], strains['e3'], 
                           strains['e4'], strains['e5'], strains['e6']]
        elastic_strain_list = [elastic_strains['e1'], elastic_strains['e2'], elastic_strains['e3'],
                             elastic_strains['e4'], elastic_strains['e5'], elastic_strains['e6']]
        
        plastic_strain_list = calculate_plastic_strain(total_strain_list, elastic_strain_list)
        
        plastic_strains = {}
        for i, key in enumerate(['e1', 'e2', 'e3', 'e4', 'e5', 'e6']):
            plastic_strains[key] = plastic_strain_list[i]
        
        return elastic_strains, plastic_strains
    
    def calculate_von_mises_quantities(self, strains: Dict[str, np.ndarray], 
                                     stresses: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate Von Mises equivalent strain and stress
        
        Args:
            strains: Dictionary with strain components
            stresses: Dictionary with stress components
            
        Returns:
            Tuple of (von_mises_strain, von_mises_stress)
        """
        strain_components = [strains['e1'], strains['e2'], strains['e3'], 
                           strains['e4'], strains['e5'], strains['e6']]
        stress_components = [stresses['s1'], stresses['s2'], stresses['s3'], 
                           stresses['s4'], stresses['s5'], stresses['s6']]
        
        von_mises_strain = calculate_von_mises_strain(strain_components)
        von_mises_stress = calculate_von_mises_stress(stress_components)
        
        return von_mises_strain, von_mises_stress
    
    def calculate_work_quantities(self, stresses: Dict[str, np.ndarray], 
                                elastic_strains: Dict[str, np.ndarray],
                                plastic_strains: Dict[str, np.ndarray],
                                volume: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Calculate work quantities (elastic and plastic)
        
        Args:
            stresses: Dictionary with stress components
            elastic_strains: Dictionary with elastic strain components
            plastic_strains: Dictionary with plastic strain components
            volume: Array of volume values
            
        Returns:
            Dictionary with work quantities
        """
        # Scale factor for work calculation (volume in m³)
        scale_factor = volume * ANGSTROM3_TO_M3
        
        # Calculate stress components list
        stress_list = [stresses['s1'], stresses['s2'], stresses['s3'], 
                      stresses['s4'], stresses['s5'], stresses['s6']]
        elastic_list = [elastic_strains['e1'], elastic_strains['e2'], elastic_strains['e3'],
                       elastic_strains['e4'], elastic_strains['e5'], elastic_strains['e6']]
        plastic_list = [plastic_strains['e1'], plastic_strains['e2'], plastic_strains['e3'],
                       plastic_strains['e4'], plastic_strains['e5'], plastic_strains['e6']]
        
        # Calculate work terms
        work_elastic_terms = calculate_work_terms(stress_list, elastic_list, 1.0)
        work_plastic_terms = calculate_work_terms(stress_list, plastic_list, 1.0)
        
        # Sum all components and apply volume scaling
        work_elastic = sum(work_elastic_terms) * scale_factor
        work_plastic = sum(work_plastic_terms) * scale_factor
        
        # Calculate cumulative work
        work_elastic_cumsum = calculate_cumulative_sum(work_elastic)
        work_plastic_cumsum = calculate_cumulative_sum(work_plastic)
        
        return {
            'work_elastic': work_elastic,
            'work_plastic': work_plastic,
            'work_elastic_cumsum': work_elastic_cumsum,
            'work_plastic_cumsum': work_plastic_cumsum
        }
    
    def calculate_energy_quantities(self, data: pd.DataFrame, volume: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Calculate energy-related quantities
        
        Args:
            data: DataFrame with simulation data
            volume: Array of volume values
            
        Returns:
            Dictionary with energy quantities
        """
        # Convert energy from eV to J and scale by volume
        energy_scale = EV_TO_J * volume * ANGSTROM3_TO_M3
        
        # Internal energy change (relative to first value)
        internal_energy = (np.array(data['u'].values) - data['u'].values[0]) * energy_scale
        
        # Heat flow (for NVE: negative kinetic energy change, for NVT: etally)
        if 'etally' in data.columns:
            # NVT ensemble
            heat_flow = np.array(data['etally'].values) * energy_scale
        else:
            # NVE ensemble - use negative kinetic energy change
            kinetic_energy = np.array(data['ek'].values) * energy_scale
            heat_flow = -(kinetic_energy - kinetic_energy[0])
        
        return {
            'internal_energy': internal_energy,
            'heat_flow': heat_flow
        }
    
    def calculate_tqc_parameters(self, work_quantities: Dict[str, np.ndarray],
                               energy_quantities: Dict[str, np.ndarray],
                               ensemble_type: str = 'nve') -> Dict[str, np.ndarray]:
        """
        Calculate Taylor-Quinney coefficient (TQC) parameters
        
        Args:
            work_quantities: Dictionary with work quantities
            energy_quantities: Dictionary with energy quantities
            ensemble_type: Type of ensemble ('nve' or 'nvt')
            
        Returns:
            Dictionary with TQC parameters
        """
        if ensemble_type.lower() == 'nve':
            beta_params = calculate_beta_parameters_nve(
                work_quantities['work_plastic_cumsum'],
                energy_quantities['heat_flow'],
                energy_quantities['internal_energy'],
                work_quantities['work_elastic_cumsum']
            )
        else:  # nvt
            beta_params = calculate_beta_parameters(
                work_quantities['work_plastic_cumsum'],
                energy_quantities['heat_flow'],
                energy_quantities['internal_energy'],
                work_quantities['work_elastic_cumsum']
            )
        
        return {
            'Beta_0_diff': beta_params[0],
            'Beta_0_int': beta_params[1],
            'Beta_1_diff': beta_params[2],
            'Beta_1_int': beta_params[3]
        }
    
    def process_complete_analysis(self, data: pd.DataFrame, 
                                ensemble_type: str = 'nve') -> pd.DataFrame:
        """
        Complete thermomechanical analysis pipeline
        
        Args:
            data: Input simulation data
            ensemble_type: Type of ensemble ('nve' or 'nvt')
            
        Returns:
            DataFrame with all calculated quantities
        """
        if self.compliance_parameters is None:
            raise ValueError("Compliance parameters not set. Call set_compliance_parameters first.")
        
        # Calculate basic quantities
        volume, volume_rate = self.calculate_volume_and_derivatives(data)
        strains = self.calculate_strain_components(data)
        stresses = self.calculate_stress_components(data, volume)
        stress_rates = self.calculate_stress_rates(stresses)
        
        # Elastic-plastic decomposition
        elastic_strains, plastic_strains = self.calculate_elastic_plastic_decomposition(strains, stress_rates)
        
        # Von Mises quantities
        von_mises_strain, von_mises_stress = self.calculate_von_mises_quantities(strains, stresses)
        von_mises_elastic, _ = self.calculate_von_mises_quantities(elastic_strains, stresses)
        von_mises_plastic, _ = self.calculate_von_mises_quantities(plastic_strains, stresses)
        
        # Work quantities
        work_quantities = self.calculate_work_quantities(stresses, elastic_strains, plastic_strains, volume)
        
        # Energy quantities
        energy_quantities = self.calculate_energy_quantities(data, volume)
        
        # TQC parameters
        tqc_parameters = self.calculate_tqc_parameters(work_quantities, energy_quantities, ensemble_type)
        
        # Assemble results
        results = pd.DataFrame({
            # Original data
            'step': data['step'],
            'l_1': data['l_1'],
            'l_2': data['l_2'], 
            'l_3': data['l_3'],
            'l_4': data['l_4'],
            'l_5': data['l_5'],
            'l_6': data['l_6'],
            'volume': volume,
            'volume_rate': volume_rate,
            
            # Strain components
            'e1': strains['e1'],
            'e2': strains['e2'],
            'e3': strains['e3'],
            'e4': strains['e4'],
            'e5': strains['e5'],
            'e6': strains['e6'],
            
            # Stress components
            's1': stresses['s1'],
            's2': stresses['s2'],
            's3': stresses['s3'],
            's4': stresses['s4'],
            's5': stresses['s5'],
            's6': stresses['s6'],
            
            # Elastic strains
            'e1_elastic': elastic_strains['e1'],
            'e2_elastic': elastic_strains['e2'],
            'e3_elastic': elastic_strains['e3'],
            'e4_elastic': elastic_strains['e4'],
            'e5_elastic': elastic_strains['e5'],
            'e6_elastic': elastic_strains['e6'],
            
            # Plastic strains
            'e1_plastic': plastic_strains['e1'],
            'e2_plastic': plastic_strains['e2'],
            'e3_plastic': plastic_strains['e3'],
            'e4_plastic': plastic_strains['e4'],
            'e5_plastic': plastic_strains['e5'],
            'e6_plastic': plastic_strains['e6'],
            
            # Von Mises quantities
            'von_mises_strain': von_mises_strain,
            'von_mises_stress': von_mises_stress,
            'von_mises_elastic': von_mises_elastic,
            'von_mises_plastic': von_mises_plastic,
            
            # Work quantities
            'work_elastic': work_quantities['work_elastic_cumsum'],
            'work_plastic': work_quantities['work_plastic_cumsum'],
            
            # Energy quantities
            'internal_energy': energy_quantities['internal_energy'],
            'heat_flow': energy_quantities['heat_flow'],
            
            # TQC parameters
            'Beta_0_diff': tqc_parameters['Beta_0_diff'],
            'Beta_0_int': tqc_parameters['Beta_0_int'],
            'Beta_1_diff': tqc_parameters['Beta_1_diff'],
            'Beta_1_int': tqc_parameters['Beta_1_int']
        })
        
        self.processed_data = results
        return results
    
    def filter_and_analyze(self, threshold: float = 0.002, 
                          analysis_columns: Optional[List[str]] = None) -> Dict:
        """
        Filter data by strain threshold and calculate final statistics
        
        Args:
            threshold: Strain threshold for filtering
            analysis_columns: Columns to analyze (default: TQC parameters)
            
        Returns:
            Dictionary with filtered data and statistics
        """
        if self.processed_data is None:
            raise ValueError("No processed data available. Run process_complete_analysis first.")
        
        if analysis_columns is None:
            analysis_columns = ['Beta_0_diff', 'Beta_0_int', 'Beta_1_diff', 'Beta_1_int']
        
        # Filter data below threshold
        filtered_data = filter_data_by_threshold(self.processed_data, 'von_mises_strain', threshold)
        
        # Calculate averages above threshold
        averages = calculate_averages_above_threshold(
            self.processed_data, 'von_mises_strain', threshold, analysis_columns
        )
        
        return {
            'filtered_data': filtered_data,
            'final_averages': averages,
            'threshold_used': threshold
        }
    
    def save_results(self, output_path: str, include_filtered: bool = False, 
                    threshold: float = 0.002) -> bool:
        """
        Save analysis results to file
        
        Args:
            output_path: Path for output file
            include_filtered: Whether to include filtered analysis
            threshold: Strain threshold for filtering
            
        Returns:
            True if save successful, False otherwise
        """
        if self.processed_data is None:
            raise ValueError("No processed data available. Run process_complete_analysis first.")
        
        try:
            # Save main results
            write_output_file(self.processed_data, output_path)
            
            # Save filtered analysis if requested
            if include_filtered:
                analysis = self.filter_and_analyze(threshold)
                
                # Create summary file
                summary_path = output_path.replace('.csv', '_summary.txt').replace('.txt', '_summary.txt')
                with open(summary_path, 'w') as f:
                    f.write(f"Thermomechanical Analysis Summary\n")
                    f.write(f"{'='*40}\n\n")
                    f.write(f"Strain threshold: {threshold}\n")
                    f.write(f"Filtered data points: {len(analysis['filtered_data'])}\n\n")
                    f.write("Final averages (above threshold):\n")
                    for key, value in analysis['final_averages'].items():
                        f.write(f"{key}: {value:.6f}\n")
                
                print(f"✅ Summary written to {summary_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving results: {str(e)}")
            return False
    
    def close_connections(self):
        """Close SFTP connections"""
        if self.sftp_manager:
            self.sftp_manager.close()
