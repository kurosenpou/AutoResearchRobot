#!/usr/bin/env python3
"""
File I/O utilities for reading various data formats
Supports both local and remote files, CSV and TXT formats
"""

import pandas as pd
import os
import tempfile
from typing import List, Optional
from ..config.constants import SUPPORTED_FORMATS, CSV_DELIMITER, DEFAULT_DELIMITER, COMMENT_CHAR
from .sftp_utils import is_remote_path, download_remote_file


def determine_file_format(file_path: str) -> str:
    """
    Determine file format based on extension
    
    Args:
        file_path: Path to the file
        
    Returns:
        File format ('csv' or 'txt')
    """
    extension = os.path.splitext(file_path.lower())[1]
    if extension == '.csv':
        return 'csv'
    elif extension in SUPPORTED_FORMATS:
        return 'txt'
    else:
        # Default to txt for unknown extensions
        return 'txt'


def read_data_file(file_path: str, headers: List[str], **kwargs) -> pd.DataFrame:
    """
    Read data file with automatic format detection
    
    Args:
        file_path: Path to the file (local or remote SFTP URL)
        headers: Column headers for the data
        **kwargs: Additional arguments for pandas read_csv
        
    Returns:
        DataFrame containing the data
        
    Raises:
        Exception: If file reading fails
    """
    temp_file_path = None
    
    try:
        # Handle remote files
        if is_remote_path(file_path):
            temp_file_path = download_remote_file(file_path)
            if temp_file_path is None:
                raise Exception("Failed to download remote file")
            actual_file_path = temp_file_path
        else:
            actual_file_path = file_path
        
        # Check if file exists
        if not os.path.exists(actual_file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine format and read accordingly
        file_format = determine_file_format(actual_file_path)
        
        # Set default parameters
        read_params = {
            'comment': COMMENT_CHAR,
            'names': headers,
            **kwargs
        }
        
        if file_format == 'csv':
            read_params['sep'] = CSV_DELIMITER
        else:  # txt format
            read_params['delim_whitespace'] = True
        
        # Read the file
        data = pd.read_csv(actual_file_path, **read_params)
        
        print(f"✅ Successfully read {len(data)} rows from {os.path.basename(file_path)}")
        return data
        
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {str(e)}")
        raise
    
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                print(f"⚠️ Warning: Could not delete temporary file: {e}")


def write_output_file(data: pd.DataFrame, output_path: str, separator: str = '\t') -> bool:
    """
    Write processed data to output file
    
    Args:
        data: DataFrame to write
        output_path: Path for output file
        separator: Column separator (default: tab)
        
    Returns:
        True if write successful, False otherwise
    """
    try:
        data.to_csv(output_path, sep=separator, index=False)
        print(f"✅ Results written to {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error writing output file: {str(e)}")
        return False


def validate_file_access(file_path: str) -> bool:
    """
    Validate that a file can be accessed
    
    Args:
        file_path: Path to validate (local or remote)
        
    Returns:
        True if file can be accessed, False otherwise
    """
    if is_remote_path(file_path):
        # For remote files, we can't validate without downloading
        # Return True and let the actual download handle errors
        return True
    else:
        return os.path.exists(file_path) and os.path.isfile(file_path)
