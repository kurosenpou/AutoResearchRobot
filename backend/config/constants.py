#!/usr/bin/env python3
"""
Configuration module for OVITO workflow backend
Contains constants and configuration settings
"""

# Energy conversion constants
EV_TO_J = 1.602e-19  # eV to Joules
ANGSTROM3_TO_M3 = 1e-30  # Å³ to m³

# Material properties (default for Aluminum)
MATERIAL_DENSITY = 1000  # kg/m³
SPECIFIC_HEAT = 903  # J/(kg·K)

# Numerical constants
SMALL_NUMBER = 1e-25  # For division protection

# SFTP connection settings
DEFAULT_SFTP_PORT = 22
OTP_LENGTH = 6

# File format settings
SUPPORTED_FORMATS = ['.txt', '.csv']
DEFAULT_DELIMITER = ' '
CSV_DELIMITER = ','
COMMENT_CHAR = '#'

# Column headers for different data types
ELASTIC_CONSTANT_HEADERS = [
    "delta_exx", "delta_eyy", "delta_ezz", "delta_exy", "delta_eyz", "delta_exz", 
    "delta_pxx", "delta_pyy", "delta_pzz", "delta_pxy", "delta_pyz", "delta_pxz"
]

NVE_DATA_HEADERS = [
    "step", "l_1", "l_2", "l_3", "l_4", "l_5", "l_6", 
    "p_1", "p_2", "p_3", "p_4", "p_5", "p_6", 
    "vol", "ep", "ek", "u", "t", "rho", "entropy"
]

NVT_DATA_HEADERS = [
    "step", "l_1", "l_2", "l_3", "l_4", "l_5", "l_6", 
    "p_1", "p_2", "p_3", "p_4", "p_5", "p_6", 
    "vol", "ep", "ek", "u", "t", "rho", "entropy", "etally"
]

OUTPUT_HEADERS = [
    "#step", "#e_xz", "#s_xz", "#dW", "#W", "#We", "#Wp", "#dWp", "#dWe", 
    "#Delta_Ep", "#Delta_Ek", "#Delta_U", "#Delta_T", "#Delta_Q", 
    "#Delta_Etot", "#Delta_Ttally", "#dQ", "#dU", 
    "#Beta_0_diff", "#Beta_0_int", "#Beta_1_diff", "#Beta_1_int"
]

# Elastic constant file names
ELASTIC_FILES = [
    "c1144.txt", "c2255.txt", "c3366.txt", 
    "c1144r.txt", "c2255r.txt", "c3366r.txt"
]

# Processing thresholds
STRAIN_FILTER_THRESHOLD = 0.002
ELASTIC_ANALYSIS_THRESHOLD = 0.002
BETA_ANALYSIS_THRESHOLD = 0.2
