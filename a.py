import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import io
import re
import os
from supabase import create_client, Client
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

# إعداد Supabase من environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "uploads"

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ لم يتم تكوين مفاتيح Supabase. تأكد من إضافة المتغيرات البيئة SUPABASE_URL و SUPABASE_KEY")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="رفع ملفات الطلاب", page_icon="📤", layout="centered")

st.markdown(
    "<h1 style='text-align: center; color: #4CAF50;'>رفع ملفات الطلاب وتحويلها</h1>"
    "<p style='text-align: center; color: #555;'>اختَر ملف ASPX وسيتم تحويله ورفعه تلقائياً إلى Supabase</p>",
    unsafe_allow_html=True
)

uploaded_file = st.file_uploader("📂 اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        with st.spinner("⏳ جاري معالجة الملف ورفعه..."):
            content = uploaded_file.read().decode("utf-8")
            soup = BeautifulSoup(content, "html.parser")
            tables = soup.find_all("table")

            all_rows = []
            current_semester, current_year = "", ""

            # محاولة استخراج معلومات الطالب
            text_content = soup.get_text()
            student_name_match = re.search(r'اسم الطالب\s*:\s*(\S.*)', text_content)
            student_id_match = re.search(r'الرقم الجامعي\s*:\s*(\S+)', text_content)
            major_match = re.search(r'التخصص\s*:\s*(\S.*)', text_content)

            student_name = student_name_match.group(1).strip() if student_name_match else "غير معروف"
            student_id = student_id_match.group(1).strip() if student_id_match else "غير معروف"
            major = major_match.group(1).strip() if major_match else "غير معروف"

            for table in tables:
                title_td = table.find("td", colspan=True)
                if title_td:
                    if all_rows:
                        all_rows.append([""] * 100)  # صف فارغ
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
                    all_rows.append([current_semester, current_year] + cells)

            if all_rows:
                max_cols = max(len(r) for r in all_rows)
                for r in all_rows:
                    while len(r) < max_cols:
                        r.append("")

                columns = ["اسم الطالب", "الرقم الجامعي", "التخصص", "الفصل الدراسي", "السنة الدراسية"] + [f"Column{i}" for i in range(1, max_cols - 4)]
                all_rows_with_student = [[student_name, student_id, major] + row for row in all_rows]
                df = pd.DataFrame(all_rows_with_student, columns=columns)

                # حفظ الـ Excel في الذاكرة أولاً
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False)
                excel_buffer.seek(0)

                # فتح الملف باستخدام openpyxl لتلوين الفصول
                wb = load_workbook(excel_buffer)
                ws = wb.active

                fill_colors = ["FFFF99", "CCFFCC", "FFCCCC", "CCE5FF", "FFCCFF", "FFFFCC"]  # ألوان مختلفة
                color_map = {}
                color_index = 0

                for row in range(2, ws.max_row + 1):  # تجاهل العنوان
                    semester_cell = ws.cell(row=row, column=4).value
                    if semester_cell and semester_cell.strip():  # إذا فيه فصل
                        if semester_cell not in color_map:
                            color_map[semester_cell] = fill_colors[color_index % len(fill_colors)]
                            color_index += 1
                        fill = PatternFill(start_color=color_map[semester_cell], end_color=color_map[semester_cell], fill_type="solid")
                        for col in range(1, ws.max_column + 1):
                            ws.cell(row=row, column=col).fill = fill

                # إعادة كتابة الملف في الذاكرة
                excel_buffer_colored = io.BytesIO()
                wb.save(excel_buffer_colored)
                excel_buffer_colored.seek(0)

                file_name = uploaded_file.name.replace(".aspx", ".xlsx")

                res = supabase.storage.from_(BUCKET_NAME).upload(
                    file_name,
                    excel_buffer_colored.getvalue(),
                    {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                )

                if "error" in str(res).lower():
                    st.error("❌ حدث خطأ أثناء رفع الملف إلى Supabase.")
                else:
                    st.success(f"✅ تم رفع الملف بنجاح! {file_name}")

            else:
                st.warning("⚠️ لم يتم العثور على أي بيانات في الملف.")

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء معالجة الملف: {e}")
