import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
from supabase import create_client, Client

# --- إعداد Supabase (لا تضع المفاتيح هنا مباشرة عند النشر على Render)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
BUCKET_NAME = "uploads"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("Collect Student Data")
st.markdown("📤 اختر ملف ASPX لكل طالب")

# حقل إضافة بيانات الطالب
student_name = st.text_input("Student Name")
student_id = st.text_input("Student ID")
student_major = st.text_input("Major")

uploaded_file = st.file_uploader("Upload ASPX file", type=["aspx"])

if uploaded_file and student_name and student_id and student_major:
    try:
        content = uploaded_file.read().decode("utf-8")
        soup = BeautifulSoup(content, "html.parser")
        tables = soup.find_all("table")

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
                
                # إضافة صف فارغ قبل كل فصل جديد
                if all_rows:
                    all_rows.append([""] * (len(all_rows[0])))
                continue

            for tr in table.find_all("tr"):
                if tr.find("td", colspan=True):
                    continue
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if not cells:
                    continue
                all_rows.append([current_semester, current_year] + cells)

        if not all_rows:
            st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")
        else:
            # تحديد أكبر عدد أعمدة في كل الصفوف
            max_cols = max(len(r) for r in all_rows)
            for r in all_rows:
                while len(r) < max_cols:
                    r.append("")

            # إنشاء أسماء الأعمدة
            columns = ["Semester", "Year"] + [f"Column{i}" for i in range(1, max_cols - 1)]
            df = pd.DataFrame(all_rows, columns=columns)

            # إضافة بيانات الطالب
            df.insert(0, "Major", student_major)
            df.insert(0, "Student ID", student_id)
            df.insert(0, "Student Name", student_name)

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
        st.error(f"❌ حدث خطأ أثناء معالجة الملف: {e}")
else:
    st.info("Please fill in student info and upload a file.")

