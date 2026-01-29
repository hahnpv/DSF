
import pandas as pd
import numpy as np
import h5py

def load_csv_trajectory(filepath, x_col='xyz_e_0', y_col='xyz_e_1', z_col='xyz_e_2'):
    """
    Loads trajectory data from a CSV file.
    
    Args:
        filepath (str): Path to CSV.
        x_col, y_col, z_col (str): Column names for position.
        
    Returns:
        np.ndarray: Nx3 array of points.
    """
    try:
        # Read first few lines to detect if there's a unit row
        # Heuristic: if row 1 contains 'm', 'kg', 'sec', etc, it's a unit row.
        # But for simplicity, let's just use the 'header' argument if we know the format.
        # Alternatively, read all, then drop non-numeric.
        
        df = pd.read_csv(filepath)
        
        # Check if the first row is units (contains strings in numeric columns)
        # We'll try to convert to numeric, coercing errors to NaN, then drop NaNs
        # But we need to identify columns first.
        
        # Actually, let's just attempt to convert everything to numeric after loading
        # This will turn "m", "kg" into NaN, which we can then drop.
        
        # Check if default columns exist, if not try to guess or inform user
        if x_col not in df.columns:
            # Fallback search for common names
            candidates = [['x', 'y', 'z'], 
                          ['X', 'Y', 'Z'],
                          ['xyz_i_0', 'xyz_i_1', 'xyz_i_2'],
                          ['xe', 'ye', 'ze'],
                          ['Earth XYZ (x)', 'Earth XYZ (y)', 'Earth XYZ (z)'], # Common in recent logs
                          ['Earth XYZ (x) ', 'Earth XYZ (y) ', 'Earth XYZ (z) '] # Trailing spaces
                         ]
            
            for c in candidates:
                # Strip spaces from df columns for robust matching
                df_cols_stripped = [col.strip() for col in df.columns]
                c_stripped = [col.strip() for col in c]
                
                # Check exact match first
                if all(col in df.columns for col in c):
                    x_col, y_col, z_col = c
                    print(f"Auto-detected columns: {x_col}, {y_col}, {z_col}")
                    break
                
                # Check stripped match
                if all(col in df_cols_stripped for col in c_stripped):
                    # Find the actual column names
                    x_col = df.columns[df_cols_stripped.index(c_stripped[0])]
                    y_col = df.columns[df_cols_stripped.index(c_stripped[1])]
                    z_col = df.columns[df_cols_stripped.index(c_stripped[2])]
                    print(f"Auto-detected columns (stripped): {x_col}, {y_col}, {z_col}")
                    break
        
        if x_col not in df.columns:
            raise ValueError(f"Could not find position columns. Defaults: {x_col}, {y_col}, {z_col}")
            
        # Extract and clean data
        subset = df[[x_col, y_col, z_col]].copy()
        
        # Coerce to numeric (errors='coerce' will turn 'kg', 'm' etc into NaN)
        subset = subset.apply(pd.to_numeric, errors='coerce')
        
        # Drop rows with NaNs
        subset = subset.dropna()
        
        data = subset.to_numpy()
        return data

    except Exception as e:
        print(f"Error loading CSV {filepath}: {e}")
        return None

def load_h5_trajectory(filepath, dataset_path='trajectory'):
    """
    Loads trajectory data from an H5 file.
    
    Args:
        filepath (str): Path to H5 file.
        dataset_path (str): Path to the dataset within the H5 file.
        
    Returns:
        np.ndarray: Nx3 array.
    """
    try:
        with h5py.File(filepath, 'r') as f:
            if dataset_path in f:
                data = f[dataset_path][:]
                # specific handling if shape is (3, N) -> transpose to (N, 3)
                if data.shape[0] == 3 and data.shape[1] > 3:
                     data = data.T
                return data
            else:
                # Try to find *any* dataset that looks like trajectory
                # This is a naive heuristic
                for key in f.keys():
                    d = f[key]
                    if hasattr(d, 'shape') and (d.shape[1] == 3 or d.shape[0] == 3):
                        print(f"Auto-selected dataset: {key}")
                        data = d[:]
                        if data.shape[0] == 3: data = data.T
                        return data
                print(f"Dataset {dataset_path} not found in {filepath}")
                return None
    except Exception as e:
        print(f"Error loading H5 {filepath}: {e}")
        return None
