import pandas as pd

def generate_daily_schedule_full_capacity(master_po, mold_inventory, cycle_time, saturday_cycle, include_sunday, sunday_cycle, start_date):
    daily_schedule = {}
    calendar_week_map = {}
    color_schedule = {}
    po_last_production_day = {}  # Track the last scheduled production day for each PO

    start_date = pd.to_datetime(start_date)

    unique_xfd = sorted(master_po["XFD"].dropna().unique())
    xfd_colors = {xfd: f"color-{i % 16}" for i, xfd in enumerate(unique_xfd)}

    non_size_columns = ["PO DATE", "Factory", "PO#NO", "sku", "COLOR TOP", "XFD", "Customer RTA", "QTY", "Blc Del 1/24"]
    size_columns = [col for col in master_po.columns if col not in non_size_columns and pd.api.types.is_numeric_dtype(master_po[col])]

    # Track the latest production date for each PO
    po_production_dates = {po: [] for po in master_po["PO#NO"].unique()}

    for size in size_columns:
        molds = mold_inventory.loc[mold_inventory['Size'] == float(size), 'Mold Count'].values
        molds = molds[0] if len(molds) > 0 else 0

        if molds == 0:
            continue

        current_date = start_date
        remaining_qty = master_po[size].sum()

        while remaining_qty > 0:
            weekday = current_date.weekday()

            if weekday == 5:  # Saturday
                daily_capacity = molds * saturday_cycle
            elif weekday == 6:  # Sunday
                if not include_sunday:
                    current_date += pd.Timedelta(days=1)
                    continue
                daily_capacity = molds * sunday_cycle
            else:
                daily_capacity = molds * cycle_time

            if current_date not in daily_schedule:
                daily_schedule[current_date] = {}
                calendar_week_map[current_date] = current_date.isocalendar()[1]

            produced_today = min(daily_capacity, remaining_qty)
            daily_schedule[current_date][size] = produced_today

            for index, row in master_po.iterrows():
                po_number = row["PO#NO"]

                if row[size] > 0:
                    if row[size] <= produced_today:
                        produced_today -= row[size]
                        master_po.at[index, size] = 0
                        color_schedule[(current_date.strftime('%Y-%m-%d'), size)] = row["XFD"]

                        # Track the last production day for this PO
                        po_production_dates[po_number].append(current_date.strftime('%Y-%m-%d'))

                    else:
                        master_po.at[index, size] -= produced_today
                        color_schedule[(current_date.strftime('%Y-%m-%d'), size)] = row["XFD"]
                        produced_today = 0
                        break

            remaining_qty -= daily_capacity
            current_date += pd.Timedelta(days=1)

    daily_schedule_df = pd.DataFrame.from_dict(daily_schedule, orient="index").fillna(0)
    daily_schedule_df = daily_schedule_df.round(0)
    daily_schedule_df.index.name = "Date"

    # Assign the latest production date for each PO as the correct completion date
    master_po["Completion Date"] = master_po["PO#NO"].map(lambda po: max(po_production_dates[po]) if po_production_dates[po] else None)

    return daily_schedule_df, calendar_week_map, color_schedule, xfd_colors, master_po
