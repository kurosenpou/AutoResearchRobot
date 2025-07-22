#!/usr/bin/env python3
"""
Core module for elastic constants calculations
Provides functionality to calculate elastic constants from stress-strain data
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from typing import Tuple, List, Dict, Optional
import os
import tempfile

from ..utils.sftp_utils import SFTPManager
from ..utils.file_utils import read_data_file
from ..config.constants import ELASTIC_CONSTANT_HEADERS


class ElasticConstantsProcessor:
    """
    Processor for elastic constants calculation from stress-strain data
    """
    
    def __init__(self, sftp_config: Optional[Dict] = None):
        """
        Initialize elastic constants processor
        
        Args:
            sftp_config: SFTP configuration dictionary
        """
        self.sftp_manager = SFTPManager() if sftp_config else None
        self.rigidity_matrix = None
        self.compliance_matrix = None
        
    def load_stress_strain_data(self, file_path: str, remote: bool = False) -> pd.DataFrame:
        """
        Load stress-strain data from file
        
        Args:
            file_path: Path to the stress-strain data file
            remote: Whether to load from remote server
            
        Returns:
            DataFrame with stress-strain data
        """
        if remote and self.sftp_manager:
            # Download and process remote file
            username, hostname, remote_path = self.sftp_manager.parse_sftp_url(file_path)
            if self.sftp_manager.authenticate(hostname, username):
                with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
                    temp_path = temp_file.name
                self.sftp_manager.download_file(remote_path, temp_path)
                data = read_data_file(temp_path, ELASTIC_CONSTANT_HEADERS)
                os.unlink(temp_path)  # Clean up temp file
                self.sftp_manager.close()
                return data
            else:
                raise Exception("Failed to authenticate to remote server")
        else:
            return read_data_file(file_path, ELASTIC_CONSTANT_HEADERS)
    
    def calculate_elastic_constant(self, stress_strain_data: pd.DataFrame, 
                                 stress_col: str, strain_col: str) -> float:
        """
        Calculate elastic constant from stress-strain data using linear regression
        
        Args:
            stress_strain_data: DataFrame with stress and strain data
            stress_col: Name of stress column
            strain_col: Name of strain column
            
        Returns:
            Elastic constant value (slope of stress-strain curve)
        """
        if stress_col not in stress_strain_data.columns or strain_col not in stress_strain_data.columns:
            raise ValueError(f"Required columns {stress_col}, {strain_col} not found in data")
        
        # Prepare data for linear regression
        strain = np.array(stress_strain_data[strain_col].values).reshape(-1, 1)
        stress = np.array(stress_strain_data[stress_col].values)
        
        # Fit linear regression (force intercept through origin for elastic constants)
        model = LinearRegression(fit_intercept=False)
        model.fit(strain, stress)
        
        return model.coef_[0]
    
    def process_elastic_constants_from_files(self, file_paths: List[str], 
                                           remote: bool = False) -> Dict[str, float]:
        """
        Process multiple elastic constant files and extract constants
        
        Args:
            file_paths: List of file paths for elastic constant data
            remote: Whether files are on remote server
            
        Returns:
            Dictionary mapping file identifiers to elastic constants
        """
        elastic_constants = {}
        
        for file_path in file_paths:
            # Extract identifier from filename (e.g., 'c1144' from 'c1144.txt')
            file_name = os.path.basename(file_path)
            identifier = os.path.splitext(file_name)[0]
            
            try:
                # Load data
                data = self.load_stress_strain_data(file_path, remote)
                
                # Calculate elastic constant (assuming standard stress-strain columns)
                if len(data.columns) >= 2:
                    strain_col = data.columns[0]  # First column is strain
                    stress_col = data.columns[1]  # Second column is stress
                    
                    constant = self.calculate_elastic_constant(data, stress_col, strain_col)
                    elastic_constants[identifier] = constant
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
                
        return elastic_constants
    
    def build_rigidity_matrix(self, elastic_constants: Dict[str, float]) -> np.ndarray:
        """
        Build 6x6 rigidity matrix from elastic constants
        
        Args:
            elastic_constants: Dictionary of elastic constants
            
        Returns:
            6x6 rigidity matrix
        """
        # Extract constants
        c11 = elastic_constants.get('c1144', 0)  # Note: this maps to C11 based on file naming
        c22 = elastic_constants.get('c2255', 0)  # C22
        c33 = elastic_constants.get('c3366', 0)  # C33
        c12 = elastic_constants.get('c1255', 0)  # C12
        c13 = elastic_constants.get('c1366', 0)  # C13
        c23 = elastic_constants.get('c2366', 0)  # C23
        
        # For cubic crystals, we need to determine C44
        # Assuming isotropic material: C44 = (C11 - C12) / 2
        c44 = (c11 - c12) / 2 if c11 > c12 else elastic_constants.get('c4455', 0)
        
        # Build symmetric rigidity matrix
        rigidity = np.array([
            [c11, c12, c13,   0,   0,   0],
            [c12, c22, c23,   0,   0,   0],
            [c13, c23, c33,   0,   0,   0],
            [  0,   0,   0, c44,   0,   0],
            [  0,   0,   0,   0, c44,   0],
            [  0,   0,   0,   0,   0, c44]
        ])
        
        self.rigidity_matrix = rigidity
        return rigidity
    
    def calculate_compliance_matrix(self, rigidity_matrix: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Calculate compliance matrix as inverse of rigidity matrix
        
        Args:
            rigidity_matrix: 6x6 rigidity matrix (uses stored matrix if None)
            
        Returns:
            6x6 compliance matrix
        """
        if rigidity_matrix is None:
            rigidity_matrix = self.rigidity_matrix
            
        if rigidity_matrix is None:
            raise ValueError("No rigidity matrix available. Build rigidity matrix first.")
        
        try:
            compliance = np.linalg.inv(rigidity_matrix)
            self.compliance_matrix = compliance
            return compliance
        except np.linalg.LinAlgError:
            raise ValueError("Rigidity matrix is singular and cannot be inverted")
    
    def get_compliance_parameters(self) -> Tuple[float, float, float]:
        """
        Extract key compliance parameters (S11, S12, S44) from compliance matrix
        
        Returns:
            Tuple of (S11, S12, S44) compliance values
        """
        if self.compliance_matrix is None:
            raise ValueError("No compliance matrix available. Calculate compliance matrix first.")
        
        S11 = self.compliance_matrix[0, 0]
        S12 = self.compliance_matrix[0, 1]
        S44 = self.compliance_matrix[3, 3]
        
        return S11, S12, S44
    
    def process_complete_elastic_analysis(self, file_paths: List[str], 
                                        remote: bool = False) -> Dict:
        """
        Complete elastic analysis pipeline
        
        Args:
            file_paths: List of elastic constant data files
            remote: Whether files are on remote server
            
        Returns:
            Dictionary with elastic constants, rigidity matrix, compliance matrix, and parameters
        """
        # Calculate elastic constants
        elastic_constants = self.process_elastic_constants_from_files(file_paths, remote)
        
        # Build rigidity matrix
        rigidity = self.build_rigidity_matrix(elastic_constants)
        
        # Calculate compliance matrix
        compliance = self.calculate_compliance_matrix(rigidity)
        
        # Get compliance parameters
        S11, S12, S44 = self.get_compliance_parameters()
        
        return {
            'elastic_constants': elastic_constants,
            'rigidity_matrix': rigidity,
            'compliance_matrix': compliance,
            'compliance_parameters': {
                'S11': S11,
                'S12': S12,
                'S44': S44
            }
        }
    
    def close_connections(self):
        """Close SFTP connections"""
        if self.sftp_manager:
            self.sftp_manager.close()


def load_elastic_constants_from_directory(directory_path: str, 
                                        pattern: str = "c*.txt",
                                        remote: bool = False,
                                        sftp_config: Optional[Dict] = None,
                                        file_list: Optional[List[str]] = None) -> Dict:
    """
    Load all elastic constant files from a directory
    
    Args:
        directory_path: Path to directory containing elastic constant files
        pattern: File pattern to match
        remote: Whether directory is on remote server
        sftp_config: SFTP configuration if remote
        
    Returns:
        Complete elastic analysis results
    """
    processor = ElasticConstantsProcessor(sftp_config)
    
    try:
        if remote:
            # For remote files, use provided file list or default names
            if file_list:
                file_paths = [f"{directory_path}/{f}" if not f.startswith(directory_path) else f for f in file_list]
            else:
                # Default elastic constant files
                default_files = ['c1144.txt', 'c2255.txt', 'c3366.txt', 'c1255.txt', 'c1366.txt', 'c2366.txt']
                file_paths = [f"{directory_path}/{f}" for f in default_files]
        else:
            # List local files
            import glob
            pattern_path = os.path.join(directory_path, pattern)
            file_paths = glob.glob(pattern_path)
        
        return processor.process_complete_elastic_analysis(file_paths, remote)
    
    finally:
        processor.close_connections()
