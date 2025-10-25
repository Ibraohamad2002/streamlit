import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
from supabase import create_client, Client

# -------------------------------
# إعداد Supabase مباشرة في الكود
# -------------------------------
SUPABASE_URL = "https://ociaekhyqtiintzguudo.supabase.co"  # غيّر إلى رابط مشروعك
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jaWFla2h5cXRpaW50emd1dWRvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEzMjI0OTAsImV4cCI6MjA3Njg5ODQ5MH0.7yeAbnv2KUqaAvbyxr8mRvpG9oALl4k9mmJd3_UmwCU"
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# واجهة Streamlit
# -------------------------------
st.title("📤 Upload Student ASPX File")

uploaded_file = st.file_uploader("اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        all_rows = []
        current_semester, current_year = "", ""
        student_name, student_id, student_major = "", "", ""

        for table in tables:
            # استخراج عنوان الفصل
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

                # محاولة استخراج معلومات الطالب من أول صفوف الجدول
                if not student_name and "الاسم" in cells[0]:
                    student_name = cells[1] if len(cells) > 1 else ""
                if not student_id and "الرقم الجامعي" in cells[0]:
                    student_id = cells[1] if len(cells) > 1 else ""
                if not student_major and "التخصص" in cells[0]:
                    student_major = cells[1] if len(cells) > 1 else ""

                all_rows.append([current_semester, current_year] + cells)
            # ترك فراغ بعد كل فصل
            all_rows.append([])

        if not all_rows:
            st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")
        else:
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")

            columns = ["الفصل الدراسي", "السنة الدراسية"] + [f"Column{i}" for i in range(1, max_cols-1)]
            df = pd.DataFrame(all_rows, columns=columns)

            # إضافة معلومات الطالب على رأس الجدول
            info_df = pd.DataFrame([[f"Student Name: {student_name}", f"Student ID: {student_id}", f"Major: {student_major}"] + [""]*(max_cols-3)], columns=columns)
            final_df = pd.concat([info_df, df], ignore_index=True)

            # حفظ Excel في الذاكرة
            excel_buffer = io.BytesIO()
            final_df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            file_name = uploaded_file.name.replace(".aspx", ".xlsx")

            # رفع الملف على Supabase
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
        st.error(f"❌ حدث خطأ أثناء معالجة الملف: {e}")
