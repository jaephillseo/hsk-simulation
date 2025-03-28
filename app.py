from flask import Flask, request, render_template, send_file
import os
import pandas as pd
from services.parsing import parse_excel, parse_mold_inventory
from services.scheduling import generate_daily_schedule_full_capacity

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#Path to store the generated Excel File
GENERATED_FILE_PATH = "outputs/daily_schedule.xlsx"
os.makedirs("outputs", exist_ok=True)

# Hardcoded Colors for 16 unique XFDs
# CSS class names for web display
CSS_COLORS = [
    "color-0", "color-1", "color-2", "color-3", "color-4",
    "color-5", "color-6", "color-7", "color-8", "color-9",
    "color-10", "color-11", "color-12", "color-13", "color-14", "color-15"
]

# Corresponding Excel Hex Colors
EXCEL_COLORS = [
    "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF",
    "#00FFFF", "#800000", "#808000", "#008000", "#800080",
    "#008080", "#000080", "#C0C0C0", "#808080", "#999999", "#666666"
]
@app.route('/')
def upload_page():
    """
    Render the upload page for master PO file.
    """
    return render_template('upload.html')

@app.route('/daily_schedule', methods=['POST'])
def daily_schedule():
    """
    Process the uploaded master PO file and generate the daily schedule.
    """
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    if file.filename == '':
        return "No file selected", 400

    # Retrieve form inputs
    cycle_time = int(request.form.get("cycle_time", 50))
    saturday_cycle = int(request.form.get("saturday_cycle", 50))
    include_sunday = request.form.get("include_sunday") == "on"
    sunday_cycle = int(request.form.get("sunday_cycle", 0)) if include_sunday else 0
    start_date = request.form.get("start_date")
    sorting_option = request.form.get("sorting_option", "original")

    if not start_date:
        return "Production start date is required", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        # Parse master PO and mold inventory
        master_po, raw_mold_inventory = parse_excel(filepath)
        mold_inventory = parse_mold_inventory(raw_mold_inventory)

        # Sort master PO based on user choice
        if sorting_option == "xfd":
            master_po = master_po.sort_values(by="XFD", ascending=True, na_position="last")
        elif sorting_option == "customer_rta":
            master_po = master_po.sort_values(by="Customer RTA", ascending=True, na_position="last")

        # Generate daily schedule
        daily_schedule_df, calendar_week_map, color_schedule, xfd_colors, master_po = generate_daily_schedule_full_capacity(
            master_po, mold_inventory, cycle_time, saturday_cycle, include_sunday, sunday_cycle, start_date
        )

        # Assign colors for XFDs based on unique values
        unique_xfd = sorted(set(master_po["XFD"].dropna()))
        xfd_colors = {
            xfd: {"css": CSS_COLORS[i % len(CSS_COLORS)], "excel": EXCEL_COLORS[i % len(EXCEL_COLORS)]}
            for i, xfd in enumerate(unique_xfd)
        }

        # Map XFD colors to schedule
        for (date, size), xfd in list(color_schedule.items()):
            if xfd in xfd_colors:
                color_schedule[(date, size)] = {
                    "css": xfd_colors[xfd]["css"],
                    "excel": xfd_colors[xfd]["excel"]
                }
            else:
                color_schedule[(date, size)] = {
                    "css": "default-color",
                    "excel": "#FFFFFF"  # Default white background
                }
        
        # Save the schedule as an Excel file for download
        with pd.ExcelWriter(GENERATED_FILE_PATH, engine='xlsxwriter') as writer:
            # Get workbook and manually create worksheet
            workbook = writer.book
            worksheet = workbook.add_worksheet("Schedule")
            writer.sheets["Schedule"] = worksheet

            # Definte formats
            header_format = workbook.add_format({'bold': True, 'border': 1})
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd', 'border': 1})
            default_format = workbook.add_format({'border': 1})
            formats = {}

            current_row = 0

            # Write PO Table
            po_columns = ["ORDER NO", "Customer RTA", "XFD", "QTY", "Completion Date"]
            worksheet.write_row(current_row, 0, po_columns, header_format)
            current_row += 1

            for _, row in master_po[po_columns].iterrows():
                for col_idx, col_name in enumerate(po_columns):
                    worksheet.write(current_row, col_idx, row[col_name], default_format)
                current_row += 1
            
            #Empty Rows
            current_row += 2

            # Write XFD Legend
            worksheet.write(current_row, 0, "XFD", header_format)
            worksheet.write(current_row, 1, "Color", header_format)
            current_row += 1

            for xfd, color_info in xfd_colors.items():
                worksheet.write(current_row, 0, xfd, default_format)
                cell_format = workbook.add_format({'bg_color': color_info["excel"], 'border': 1})
                worksheet.write(current_row, 1, "", cell_format)
                current_row += 1

            #Empty Rows
            current_row += 2

            #Mold Inventory Table

            #Size Headers
            size_list = mold_inventory["Size"].tolist()
            worksheet.write_row(current_row, 0, size_list, header_format)
            current_row += 1

            #Write mold count row
            count_list = mold_inventory["Mold Count"].tolist()
            worksheet.write_row(current_row, 0, count_list, default_format)
            current_row += 1

            current_row += 2

            # Write header row
            schedule_header = ["Date"] + list(daily_schedule_df.columns)
            worksheet.write_row(current_row, 0, schedule_header, header_format)
            current_row += 1

            # Create formats
            

            for _, row_data in daily_schedule_df.iterrows():
                worksheet.write_datetime(current_row, 0, pd.to_datetime(row_data.name), date_format)

                for col_num, size in enumerate(daily_schedule_df.columns, start=1):
                    cell_value = row_data[size]
                    color_entry = color_schedule.get((row_data.name.strftime('%Y-%m-%d'), size), {})
                    excel_color = color_entry.get("excel")

                    # Pick format based on color
                    if excel_color:
                        if excel_color not in formats:
                            formats[excel_color] = workbook.add_format({'bg_color': excel_color, 'border': 1})
                        fmt = formats[excel_color]
                    else:
                        fmt = default_format

                    worksheet.write(current_row, col_num, cell_value, fmt)
                
                current_row += 1

                worksheet.set_column(0, worksheet.dim_colmax, 15)


    except Exception as e:
        return f"Error processing file: {str(e)}", 500

    # Render the schedule template
    return render_template(
        "schedule.html",
        daily_schedule=daily_schedule_df.to_dict(orient="index"),
        calendar_week_map=calendar_week_map,
        color_schedule=color_schedule,
        xfd_colors=xfd_colors,
        master_po=master_po.to_dict(orient="records")
    )

# Make str available in Jinja2 templates
app.jinja_env.globals.update(str=str)

@app.route('/download_schedule')
def download_schedule():
    return send_file(GENERATED_FILE_PATH, as_attachment=True, download_name="daily_schedule.xlsx")

if __name__ == '__main__':
    app.run(debug=True)
