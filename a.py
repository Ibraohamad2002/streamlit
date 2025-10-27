import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
from supabase import create_client, Client
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook
import time
# Supabase configuration
SUPABASE_URL = "https://ociaekhyqtiintzguudo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jaWFla2h5cXRpaW50emd1dWRvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEzMjI0OTAsImV4cCI6MjA3Njg5ODQ5MH0.7yeAbnv2KUqaAvbyxr8mRvpG9oALl4k9mmJd3_UmwCU"
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("Upload Student ASPX Files")

uploaded_file = st.file_uploader("📤 Choose an ASPX file", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        # Extract student data
        full_text = soup.get_text(separator="\n")
        student_id_match = re.search(r"رقم الطالب\s*[:\-]?\s*(.+)", full_text)
        major_match = re.search(r"التخصص\s*[:\-]?\s*(.+)", full_text)
        admission_year_match = re.search(r"سنة القبول\s*[:\-]?\s*(\d{4})", full_text)
        admission_type_match = re.search(r"نوع القبول\s*[:\-]?\s*(.+)", full_text)

        student_id = student_id_match.group(1).strip() if student_id_match else ""
        major = major_match.group(1).strip() if major_match else ""
        admission_year = admission_year_match.group(1).strip() if admission_year_match else ""
        admission_type = admission_type_match.group(1).strip() if admission_type_match else ""

        # Convert admission year to full academic year (e.g., 2020/2021)
        if admission_year:
            start_year = int(admission_year)
            end_year = start_year + 1
            admission_year_full = f"{start_year}/{end_year}"
        else:
            admission_year_full = ""

        all_rows = []

        # Iterate over all tables in the ASPX file
        for table in tables:
            title_td = table.find("td", colspan=True)
            if title_td:
                if all_rows:
                    all_rows.append([""]*4)  # Add empty row between semesters
                continue

            for i, tr in enumerate(table.find_all("tr")):
                if tr.find("td", colspan=True):
                    continue
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                # First row contains student info, other rows are empty for basic columns
                if i == 0:
                    row = [student_id, major, admission_year_full, admission_type] + cells
                else:
                    row = [""]*4 + cells
                all_rows.append(row)

        if not all_rows:
            st.warning("⚠️ No data found in the file.")
        else:
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")
            columns = ["Student ID", "Major", "Admission Year", "Admission Type"] + [f"Column{i}" for i in range(1, max_cols - 4 + 1)]
            df = pd.DataFrame(all_rows, columns=columns)

            # Save Excel file in memory
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            # Auto-adjust column widths
            wb = load_workbook(excel_buffer)
            ws = wb.active
            for col in ws.columns:
                max_length = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                ws.column_dimensions[col_letter].width = max_length + 5
            excel_buffer2 = io.BytesIO()
            wb.save(excel_buffer2)
            excel_buffer2.seek(0)

            file_name = f"{student_id}_{int(time.time())}.xlsx"

            # Upload the Excel file to Supabase Storage
            res = supabase.storage.from_(BUCKET_NAME).upload(
                file_name,
                excel_buffer2.getvalue(),
                {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
            )

            if "error" in str(res).lower():
                st.error(f"❌ Error uploading file to Supabase: {res}")
            else:
                st.success(f"✅ File successfully converted and uploaded to Supabase ({file_name})!")

    except Exception as e:
        st.error(f"❌ Processing error: {e}")

