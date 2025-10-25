import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
from supabase import create_client, Client

# ---------------- Supabase Config ----------------
SUPABASE_URL = "https://ociaekhyqtiintzguudo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jaWFla2h5cXRpaW50emd1dWRvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEzMjI0OTAsImV4cCI6MjA3Njg5ODQ5MH0.7yeAbnv2KUqaAvbyxr8mRvpG9oALl4k9mmJd3_UmwCU"
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Upload & Convert ASPX to Excel", page_icon="📤")
st.title("📤 Upload Student File")

uploaded_file = st.file_uploader("اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        all_rows = []
        current_semester, current_year = "", ""
        student_name_parts = ["", "", "", ""]
        admission_year = ""
        admission_type = ""

        for table in tables:
            info_tds = table.find_all("td", class_="student-info")
            if info_tds:
                student_name_parts = [td.get_text(strip=True) for td in info_tds[:4]]
                admission_year = info_tds[4].get_text(strip=True) if len(info_tds) > 4 else ""
                admission_type = info_tds[5].get_text(strip=True) if len(info_tds) > 5 else ""

            title_td = table.find("td", colspan=True)
            if title_td:
                title_text = title_td.get_text(strip=True)
                semester_match = re.search(r'(الفصل\s+\S+)', title_text)
                year_match = re.search(r'(\d{4}/\d{4})', title_text)
                current_semester = semester_match.group(1) if semester_match else ""
                current_year = year_match.group(1) if year_match else ""
                continue

            for tr in table.find_all("tr"):
                if tr.find("td", colspan=True):
                    continue
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                if not all_rows or all_rows[-1][0:4] != student_name_parts:
                    all_rows.append(student_name_parts + [admission_year, admission_type] + [current_semester, current_year] + cells)
                else:
                    all_rows.append([""]*4 + ["", ""] + [current_semester, current_year] + cells)

        if not all_rows:
            st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")
        else:
            # ضبط عدد الأعمدة لكل صف
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")

            # إنشاء أسماء الأعمدة بشكل ديناميكي
            base_columns = ["اسم الطالب 1", "اسم الطالب 2", "اسم الطالب 3", "اسم الطالب 4",
                            "سنة القبول", "نوع القبول",
                            "الفصل الدراسي", "السنة الدراسية"]
            extra_cols_count = max_cols - len(base_columns)
            columns = base_columns + [f"Column{i}" for i in range(1, extra_cols_count + 1)]

            # تأكيد توافق الصفوف مع الأعمدة
            for idx, r in enumerate(all_rows):
                if len(r) != len(columns):
                    if len(r) < len(columns):
                        r += [""] * (len(columns) - len(r))
                    else:
                        all_rows[idx] = r[:len(columns)]

            df = pd.DataFrame(all_rows, columns=columns)

            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            file_name = uploaded_file.name.replace(".aspx", ".xlsx")

            res = supabase.storage.from_(BUCKET_NAME).upload(
                file_name,
                excel_buffer.getvalue(),
                {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
            )

            if "error" in str(res).lower():
                st.error(f"❌ حدث خطأ أثناء رفع الملف إلى Supabase: {res}")
            else:
                st.success(f"✅ تم تحويل ورفع الملف بنجاح إلى Supabase ({file_name})!")

    except Exception as e:
        st.error(f"❌ خطأ أثناء المعالجة: {e}")
