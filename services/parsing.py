import pandas as pd

def parse_excel(filepath):
    """
    Parses the uploaded Excel file containing the Master PO and Mold Inventory.

    Args:
        filepath (str): Path to the uploaded Excel file.

    Returns:
        tuple: (Master PO DataFrame, Raw Mold Inventory DataFrame)
    """
    master_po = pd.read_excel(filepath, sheet_name="Master PO")
    mold_inventory_raw = pd.read_excel(filepath, sheet_name="Mold Inventory", header=None)
    return master_po, mold_inventory_raw

def parse_mold_inventory(mold_inventory_raw):
    """
    Parses the raw mold inventory sheet into a structured DataFrame.

    Args:
        mold_inventory_raw (DataFrame): Raw mold inventory from the Excel file.

    Returns:
        DataFrame: Parsed mold inventory with columns ['Size', 'Mold Count'].
    """
    # Extract size headers and mold counts
    size_headers = mold_inventory_raw.iloc[0].tolist()  # First row: sizes
    mold_counts = mold_inventory_raw.iloc[1].tolist()  # Second row: mold counts

    # Create DataFrame
    mold_inventory = pd.DataFrame({'Size': size_headers, 'Mold Count': mold_counts})

    # Remove invalid rows (e.g., text headers like 'QTY')
    mold_inventory = mold_inventory[mold_inventory['Size'].apply(lambda x: str(x).replace('.', '', 1).isdigit())]

    # Convert size and mold count to numeric values
    mold_inventory['Size'] = pd.to_numeric(mold_inventory['Size'], errors='coerce')
    mold_inventory['Mold Count'] = pd.to_numeric(mold_inventory['Mold Count'], errors='coerce')

    # Drop rows where conversion failed (this removes 'QTY' or any non-numeric values)
    mold_inventory = mold_inventory.dropna()

    # Convert final values to correct types
    mold_inventory['Size'] = mold_inventory['Size'].astype(float)
    mold_inventory['Mold Count'] = mold_inventory['Mold Count'].astype(int)

    return mold_inventory