import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
from supabase import create_client, Client

# إعداد Supabase
SUPABASE_URL = "ttps://ociaekhyqtiintzguudo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jaWFla2h5cXRpaW50emd1dWRvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEzMjI0OTAsImV4cCI6MjA3Njg5ODQ5MH0.7yeAbnv2KUqaAvbyxr8mRvpG9oALl4k9mmJd3_UmwCU"
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("Upload Student ASPX Files")

uploaded_file = st.file_uploader("📤 اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        # استخراج بيانات الطالب من أعلى الصفحة أو من صف محدد
        full_text = soup.get_text(separator="\n")
        name_match = re.search(r"اسم الطالب\s*[:\-]?\s*(\S.+)", full_text)
        id_match = re.search(r"رقم الطالب\s*[:\-]?\s*(\S+)", full_text)
        major_match = re.search(r"التخصص\s*[:\-]?\s*(\S.+)", full_text)
        admission_year_match = re.search(r"سنة القبول\s*[:\-]?\s*(\d{4})", full_text)
        admission_type_match = re.search(r"نوع القبول\s*[:\-]?\s*(\S+)", full_text)

        student_name = name_match.group(1).strip() if name_match else ""
        student_id = id_match.group(1).strip() if id_match else ""
        major = major_match.group(1).strip() if major_match else ""
        admission_year = admission_year_match.group(1).strip() if admission_year_match else ""
        admission_type = admission_type_match.group(1).strip() if admission_type_match else ""

        all_rows = []
        current_semester, current_year = "", ""

        for table in tables:
            title_td = table.find("td", colspan=True)
            if title_td:
                title_text = title_td.get_text(strip=True)
                semester_match = re.search(r'(الفصل\s+\S+)', title_text)
                year_match = re.search(r'(\d{4}/\d{4})', title_text)
                current_semester = semester_match.group(1) if semester_match else ""
                current_year = year_match.group(1) if year_match else ""
                # إضافة صف فارغ للفصل السابق
                if all_rows:
                    all_rows.append([""]*7)
                continue

            for tr in table.find_all("tr"):
                if tr.find("td", colspan=True):
                    continue
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                # إضافة بيانات الطالب في أول الأعمدة
                all_rows.append([student_name, student_id, major, admission_year, admission_type, current_semester, current_year] + cells)

        if not all_rows:
            st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")
        else:
            # معالجة الجداول وإنشاء ملف Excel في الذاكرة
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")
            columns = ["اسم الطالب", "رقم الطالب", "التخصص", "سنة القبول", "نوع القبول", "الفصل الدراسي", "السنة الدراسية"] + [f"Column{i}" for i in range(1, max_cols - 7 + 1)]
            df = pd.DataFrame(all_rows, columns=columns)

            # حفظ الملف في الذاكرة بصيغة Excel
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            file_name = uploaded_file.name.replace(".aspx", ".xlsx")

            # رفع الملف إلى Supabase Storage
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
