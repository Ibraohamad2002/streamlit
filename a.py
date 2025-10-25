import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
import time
from supabase import create_client, Client

# إعداد Supabase
SUPABASE_URL = "https://ociaekhyqtiintzguudo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # ضع هنا الـ anon key
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("Student File Upload")

uploaded_file = st.file_uploader("📤 اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

        all_rows = []
        current_semester, current_year = "", ""
        student_info = {}

        # محاولة استخراج بيانات الطالب من أي جدول أو عنوان
        header_text = soup.find("h1")  # إذا فيه h1 يحتوي الاسم أو الرقم
        if header_text:
            header_text = header_text.get_text()
            student_info['اسم الطالب'] = re.search(r'الاسم\s*:\s*(\S.+)', header_text)
            student_info['رقم الطالب'] = re.search(r'الرقم\s*:\s*(\d+)', header_text)
            student_info['التخصص'] = re.search(r'التخصص\s*:\s*(\S.+)', header_text)

        for table in tables:
            # استخراج عنوان الفصل والسنة
            title_td = table.find("td", colspan=True)
            if title_td:
                title_text = title_td.get_text(strip=True)
                semester_match = re.search(r'(الفصل\s+\S+)', title_text)
                year_match = re.search(r'(\d{4}/\d{4})', title_text)
                current_semester = semester_match.group(1) if semester_match else ""
                current_year = year_match.group(1) if year_match else ""

                # أضف صف فارغ قبل كل فصل ما عدا أول فصل
                if all_rows:
                    all_rows.append([""] * (len(all_rows[0])))

                continue

            for tr in table.find_all("tr"):
                if tr.find("td", colspan=True):
                    continue
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                row = [current_semester, current_year] + cells
                all_rows.append(row)

        if not all_rows:
            st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")
        else:
            # تحديد أكبر عدد أعمدة
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")

            # أسماء الأعمدة
            columns = ["الفصل الدراسي", "السنة الدراسية"] + [f"Column{i}" for i in range(1, max_cols-1)]

            df = pd.DataFrame(all_rows, columns=columns)

            # إضافة بيانات الطالب في رأس الملف
            student_meta = {
                "رقم الطالب": student_info.get('رقم الطالب').group(1) if student_info.get('رقم الطالب') else "",
                "اسم الطالب": student_info.get('اسم الطالب').group(1) if student_info.get('اسم الطالب') else "",
                "التخصص": student_info.get('التخصص').group(1) if student_info.get('التخصص') else "",
            }
            for key, value in student_meta.items():
                df[key] = value

            # حفظ الملف في الذاكرة بصيغة Excel
            excel_buffer = io.BytesIO()
            df.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            # اسم فريد للملف لتجنب Duplicate
            file_name = uploaded_file.name.replace(".aspx", f"_{int(time.time())}.xlsx")

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

