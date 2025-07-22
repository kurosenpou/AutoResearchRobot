#!/usr/bin/env python3
"""
Mathematical utilities for stress-strain calculations
Contains functions for strain calculations, stress transformations, and statistical operations
"""

import numpy as np
import pandas as pd
from typing import Tuple, List
from ..config.constants import SMALL_NUMBER


def calculate_logarithmic_strain(length_values: np.ndarray) -> np.ndarray:
    """
    Calculate logarithmic strain increments
    
    Args:
        length_values: Array of length values
        
    Returns:
        Array of strain increments with first element as 0
    """
    if len(length_values) < 2:
        return np.array([0])
    
    strain_increments = np.log(length_values[1:] / length_values[:-1])
    return np.concatenate([[0], strain_increments])


def calculate_engineering_strain(length_values: np.ndarray) -> np.ndarray:
    """
    Calculate engineering strain increments (for shear components)
    
    Args:
        length_values: Array of length values
        
    Returns:
        Array of strain increments with first element as 0
    """
    if len(length_values) < 2:
        return np.array([0])
    
    strain_increments = np.diff(length_values)
    return np.concatenate([[0], strain_increments])


def calculate_von_mises_strain(strain_components: List[np.ndarray]) -> np.ndarray:
    """
    Calculate Von Mises equivalent strain
    
    Args:
        strain_components: List of 6 strain components [e1, e2, e3, e4, e5, e6]
        
    Returns:
        Von Mises equivalent strain array
    """
    e1, e2, e3, e4, e5, e6 = strain_components
    
    von_mises = (np.sqrt(2)/3 * 
                 np.sqrt((e1 - e2)**2 + (e2 - e3)**2 + (e1 - e3)**2 + 
                         3/2 * (e4**2 + e5**2 + e6**2)))
    
    return von_mises


def calculate_von_mises_stress(stress_components: List[np.ndarray]) -> np.ndarray:
    """
    Calculate Von Mises equivalent stress
    
    Args:
        stress_components: List of 6 stress components [s1, s2, s3, s4, s5, s6]
        
    Returns:
        Von Mises equivalent stress array
    """
    s1, s2, s3, s4, s5, s6 = stress_components
    
    von_mises = np.sqrt(0.5 * ((s1 - s2)**2 + (s2 - s3)**2 + (s1 - s3)**2 + 
                               6 * (s4**2 + s5**2 + s6**2)))
    
    return von_mises


def calculate_elastic_strain(stress_rates: List[np.ndarray], 
                           compliance_matrix: Tuple[float, float, float]) -> List[np.ndarray]:
    """
    Calculate elastic strain increments using compliance matrix
    
    Args:
        stress_rates: List of 6 stress rate components
        compliance_matrix: Tuple of (S11, S12, S44) compliance values
        
    Returns:
        List of 6 elastic strain increment arrays
    """
    S11, S12, S44 = compliance_matrix
    ds1, ds2, ds3, ds4, ds5, ds6 = stress_rates
    
    elastic_strains = [
        S11 * ds1 + S12 * (ds2 + ds3),  # dee_1
        S11 * ds2 + S12 * (ds1 + ds3),  # dee_2
        S11 * ds3 + S12 * (ds1 + ds2),  # dee_3
        S44 * ds4,                       # dee_4
        S44 * ds5,                       # dee_5
        S44 * ds6                        # dee_6
    ]
    
    return elastic_strains


def calculate_plastic_strain(total_strain: List[np.ndarray], 
                           elastic_strain: List[np.ndarray]) -> List[np.ndarray]:
    """
    Calculate plastic strain as difference between total and elastic strain
    
    Args:
        total_strain: List of total strain components
        elastic_strain: List of elastic strain components
        
    Returns:
        List of plastic strain components
    """
    plastic_strains = []
    for i in range(len(total_strain)):
        plastic_strains.append(total_strain[i] - elastic_strain[i])
    
    return plastic_strains


def calculate_work_terms(stress_components: List[np.ndarray], 
                        strain_components: List[np.ndarray], 
                        scale_factor: float = 1e9) -> List[np.ndarray]:
    """
    Calculate work terms from stress and strain components
    
    Args:
        stress_components: List of stress arrays
        strain_components: List of strain arrays
        scale_factor: Scaling factor for work calculation
        
    Returns:
        List of work arrays
    """
    work_terms = []
    for i in range(len(stress_components)):
        work = scale_factor * (stress_components[i] * strain_components[i])
        work_terms.append(work)
    
    return work_terms


def calculate_cumulative_sum(incremental_values: np.ndarray) -> np.ndarray:
    """
    Calculate cumulative sum of incremental values
    
    Args:
        incremental_values: Array of incremental values
        
    Returns:
        Array of cumulative sums
    """
    return np.cumsum(incremental_values)


def calculate_beta_parameters(work_plastic: np.ndarray, 
                            heat_flow: np.ndarray, 
                            internal_energy: np.ndarray, 
                            work_elastic: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Taylor-Quinney coefficient (TQC) parameters
    
    Args:
        work_plastic: Plastic work array
        heat_flow: Heat flow array
        internal_energy: Internal energy change array
        work_elastic: Elastic work array
        
    Returns:
        Tuple of (Beta_0_diff, Beta_0_int, Beta_1_diff, Beta_1_int)
    """
    # Differential plastic work
    dWp = np.concatenate([[0], np.diff(work_plastic)])
    
    # Differential heat flow
    dQ = np.concatenate([[0], np.diff(heat_flow)])
    
    # Differential internal energy
    dU = np.concatenate([[0], np.diff(internal_energy)])
    
    # Differential elastic work
    dWe = np.concatenate([[0], np.diff(work_elastic)])
    
    # Beta parameters
    Beta_0_diff = dQ / (dWp + SMALL_NUMBER)
    Beta_0_int = heat_flow / (work_plastic + SMALL_NUMBER)
    Beta_1_diff = 1 - ((dU - dWe) / (dWp + SMALL_NUMBER))
    Beta_1_int = 1 - ((internal_energy - work_elastic) / (work_plastic + SMALL_NUMBER))
    
    return Beta_0_diff, Beta_0_int, Beta_1_diff, Beta_1_int


def calculate_beta_parameters_nve(work_plastic: np.ndarray, 
                                heat_flow: np.ndarray, 
                                internal_energy: np.ndarray, 
                                work_elastic: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate TQC parameters for NVE ensemble (includes heat flow in Beta_1)
    
    Args:
        work_plastic: Plastic work array
        heat_flow: Heat flow array
        internal_energy: Internal energy change array
        work_elastic: Elastic work array
        
    Returns:
        Tuple of (Beta_0_diff, Beta_0_int, Beta_1_diff, Beta_1_int)
    """
    # Differential plastic work
    dWp = np.concatenate([[0], np.diff(work_plastic)])
    
    # Differential heat flow
    dQ = np.concatenate([[0], np.diff(heat_flow)])
    
    # Differential internal energy
    dU = np.concatenate([[0], np.diff(internal_energy)])
    
    # Differential elastic work
    dWe = np.concatenate([[0], np.diff(work_elastic)])
    
    # Beta parameters (NVE version includes heat flow)
    Beta_0_diff = dQ / (dWp + SMALL_NUMBER)
    Beta_0_int = heat_flow / (work_plastic + SMALL_NUMBER)
    Beta_1_diff = 1 - ((dU - dWe - dQ) / (dWp + SMALL_NUMBER))
    Beta_1_int = 1 - ((internal_energy - work_elastic - heat_flow) / (work_plastic + SMALL_NUMBER))
    
    return Beta_0_diff, Beta_0_int, Beta_1_diff, Beta_1_int


def filter_data_by_threshold(data: pd.DataFrame, column: str, threshold: float) -> pd.DataFrame:
    """
    Filter dataframe by threshold value in specified column
    
    Args:
        data: Input dataframe
        column: Column name to filter by
        threshold: Threshold value
        
    Returns:
        Filtered dataframe
    """
    return data[data[column] <= threshold]


def calculate_averages_above_threshold(data: pd.DataFrame, 
                                     threshold_column: str, 
                                     threshold_value: float, 
                                     target_columns: List[str]) -> dict:
    """
    Calculate averages for specified columns where threshold column exceeds threshold
    
    Args:
        data: Input dataframe
        threshold_column: Column to apply threshold to
        threshold_value: Threshold value
        target_columns: Columns to calculate averages for
        
    Returns:
        Dictionary of column name to average value
    """
    filtered_data = data[data[threshold_column] > threshold_value]
    
    if len(filtered_data) == 0:
        return {}
    
    averages = {}
    for col in target_columns:
        if col in filtered_data.columns:
            averages[col] = filtered_data[col].mean()
    
    return averages
