import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Any

def standardize_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Analyzes, cleans, and standardizes a dataset for bias analysis.
    Returns the processed dataframe and a metadata report.
    """
    processed_df = df.copy()
    report = {
        "original_rows": len(df),
        "original_cols": len(df.columns),
        "clean_steps": [],
        "column_types": {}
    }

    # 1. Basic Cleaning
    # Drop columns that are entirely empty
    empty_cols = processed_df.columns[processed_df.isnull().all()].tolist()
    if empty_cols:
        processed_df.drop(columns=empty_cols, inplace=True)
        report["clean_steps"].append(f"Dropped empty columns: {empty_cols}")

    # 2. Clean Column Names (Readable and engine-friendly)
    original_cols = processed_df.columns.tolist()
    new_cols = {}
    for col in original_cols:
        # Convert to snake_case, remove special chars, trim
        c = str(col).strip().lower()
        # Replace spaces, dots, dashes with underscores
        for char in [' ', '.', '-', '/', '\\', '(', ')', '[', ']', '{', '}']:
            c = c.replace(char, '_')
        # Remove duplicate underscores
        while '__' in c:
            c = c.replace('__', '_')
        # Remove non-alphanumeric (except underscores)
        c = ''.join(e for e in c if e.isalnum() or e == '_')
        # Trim underscores
        c = c.strip('_')
        
        if not c: c = "column"
            
        # Ensure uniqueness
        base_name = c
        counter = 1
        while c in new_cols.values():
            c = f"{base_name}_{counter}"
            counter += 1
        new_cols[col] = c
    
    processed_df.rename(columns=new_cols, inplace=True)
    report["column_mapping"] = new_cols
    report["clean_steps"].append("Standardized column names to readable snake_case")

    # 3. Type Inference and Normalization
    for col in processed_df.columns:
        # Try to convert to numeric if possible (handles strings that are actually numbers)
        if processed_df[col].dtype == 'object':
            try:
                numeric_conv = pd.to_numeric(processed_df[col], errors='coerce')
                # If more than 80% converted successfully, we treat it as numeric
                if numeric_conv.notnull().mean() > 0.8:
                    processed_df[col] = numeric_conv
                    report["clean_steps"].append(f"Converted '{col}' to numeric")
            except:
                pass

        # Fill missing values for analysis stability
        if processed_df[col].isnull().any():
            if pd.api.types.is_numeric_dtype(processed_df[col]):
                # Fill numeric with median
                median_val = processed_df[col].median()
                processed_df[col].fillna(median_val, inplace=True)
                report["clean_steps"].append(f"Filled missing values in '{col}' with median ({median_val})")
            else:
                # Fill categorical with 'Unknown'
                processed_df[col].fillna("Unknown", inplace=True)
                report["clean_steps"].append(f"Filled missing values in '{col}' with 'Unknown'")

    # 4. Standardization of Binary Values (Yes/No, True/False, etc.)
    true_patterns = ['yes', 'true', '1', '1.0', 'approved', 'pass', 'selected', 'y']
    false_patterns = ['no', 'false', '0', '0.0', 'rejected', 'fail', 'unselected', 'n']

    for col in processed_df.columns:
        unique_vals = processed_df[col].unique()
        if len(unique_vals) == 2:
            uv_str = [str(v).lower().strip() for v in unique_vals]
            if any(v in true_patterns for v in uv_str) or any(v in false_patterns for v in uv_str):
                mapping = {}
                for v in unique_vals:
                    sv = str(v).lower().strip()
                    if sv in true_patterns: mapping[v] = 1
                    elif sv in false_patterns: mapping[v] = 0
                    else: mapping[v] = 0
                
                if len(set(mapping.values())) == 2:
                    processed_df[col] = processed_df[col].map(mapping)
                    report["clean_steps"].append(f"Mapped binary column '{col}' to 0/1")

    report["final_rows"] = len(processed_df)
    report["final_cols"] = len(processed_df.columns)
    
    return processed_df, report
