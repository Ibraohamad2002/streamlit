import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import BytesIO
from supabase import create_client, Client

# ======== إعداد Supabase ========
SUPABASE_URL = "https://ociaekhyqtiintzguudo.supabase.co"  # ضع رابط مشروعك هنا
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jaWFla2h5cXRpaW50emd1dWRvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEzMjI0OTAsImV4cCI6MjA3Njg5ODQ5MH0.7yeAbnv2KUqaAvbyxr8mRvpG9oALl4k9mmJd3_UmwCU"                       # ضع anon key هنا
BUCKET_NAME = "uploads"                    # اسم الـ bucket الذي أنشأته

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======== واجهة Streamlit ========
st.title("رفع ملفات ASPX وتحويلها إلى Excel")

uploaded_file = st.file_uploader("اختر ملف ASPX", type=["aspx"])

if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except UnicodeDecodeError:
        st.error("❌ الملف ليس بترميز UTF-8. حاول إعادة حفظه كـ UTF-8.")
        st.stop()

    soup = BeautifulSoup(content, "html.parser")
    tables = soup.find_all("table")
    st.write(f"عدد الجداول في الملف: {len(tables)}")

    all_rows = []
    current_semester = ""
    current_year = ""

    for table in tables:
        title_td = table.find("td", colspan=True)
        if title_td:
            title_text = title_td.get_text(strip=True)
            semester_match = re.search(r'(الفصل\s+\S+)', title_text)
            year_match = re.search(r'(\d{4}/\d{4})', title_text)
            if semester_match:
                current_semester = semester_match.group(1)
            else:
                current_semester = ""
            if year_match:
                current_year = year_match.group(1)
            else:
                current_year = ""
            continue

        for tr in table.find_all("tr"):
            if tr.find("td", colspan=True):
                continue
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            all_rows.append([current_semester, current_year] + cells)

    if not all_rows:
        st.warning("⚠️ لم يتم استخراج أي بيانات من الملف.")
        st.stop()

    max_cols = max(len(r) for r in all_rows)
    for r in all_rows:
        while len(r) < max_cols:
            r.append("")

    columns = ["الفصل الدراسي", "السنة الدراسية"] + [f"Column{i}" for i in range(1, max_cols-1)]
    df = pd.DataFrame(all_rows, columns=columns)

    # تحويل DataFrame إلى Excel داخل الذاكرة
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    # زر لتحميل الملف
    st.download_button(
        label="⬇️ تحميل ملف Excel",
        data=output,
        file_name=uploaded_file.name.replace(".aspx", ".xlsx"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ===== رفع الملف على Supabase =====
    try:
        output.seek(0)
        file_name = uploaded_file.name.replace(".aspx", ".xlsx")
        res = supabase.storage.from_(BUCKET_NAME).upload(file_name, output, {"cacheControl": "3600", "upsert": True})
        if res:
            st.success(f"✅ تم رفع الملف إلى Supabase: {file_name}")
    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء رفع الملف إلى Supabase: {e}")
