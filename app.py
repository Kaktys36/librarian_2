import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="Просмотр базы упоминаний", layout="wide")
st.title("📰 Просмотр базы данных упоминаний")

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect("newspapers.db")
    df = pd.read_sql_query("""
        SELECT 
            id,
            newspaper_name AS Газета,
            publication_date AS Дата,
            person_name AS Имя,
            context AS Контекст,
            pdf_filename AS Файл
        FROM newspaper_mentions
        ORDER BY publication_date, newspaper_name, person_name
    """, conn)
    conn.close()
    return df

df = load_data()

if df.empty:
    st.error("База данных пуста")
    st.stop()

# ==================== БОКОВАЯ ПАНЕЛЬ ====================
st.sidebar.header("🔍 Фильтры")

# Фильтр по имени
name_filter = st.sidebar.text_input("Поиск по имени человека", "")
if name_filter:
    df = df[df["Имя"].str.contains(name_filter, case=False, na=False)]

# Фильтр по газете — показываем ВСЕ реальные названия из базы
newspaper_list = sorted(df["Газета"].unique())
selected_newspapers = st.sidebar.multiselect(
    "Газета",
    options=newspaper_list,
    default=newspaper_list,      # по умолчанию выбраны все
    help="Можно выбрать несколько"
)

if selected_newspapers:
    df = df[df["Газета"].isin(selected_newspapers)]

# Фильтр по дате
df["Дата"] = pd.to_datetime(df["Дата"], errors='coerce')
min_date = df["Дата"].min().date()
max_date = df["Дата"].max().date()

date_range = st.sidebar.date_input(
    "Диапазон дат",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if len(date_range) == 2:
    start_date, end_date = date_range
    df = df[(df["Дата"].dt.date >= start_date) & (df["Дата"].dt.date <= end_date)]

st.sidebar.markdown(f"**Найдено записей:** {len(df)}")

# ==================== ТАБЛИЦА ====================
st.subheader(f"📋 Список упоминаний ({len(df)} записей)")

page_size = st.selectbox("Записей на странице", [20, 50, 100, 200], index=0)
page_num = st.number_input("Страница", min_value=1, value=1, step=1)

start_idx = (page_num - 1) * page_size
end_idx = start_idx + page_size
page_df = df.iloc[start_idx:end_idx].copy()

st.dataframe(
    page_df[["Имя", "Газета", "Дата", "Контекст"]],
    use_container_width=True,
    height=600,
    hide_index=True,
    column_config={
        "Имя": st.column_config.TextColumn("Имя", width="medium"),
        "Газета": st.column_config.TextColumn("Газета", width="medium"),
        "Дата": st.column_config.DateColumn("Дата", format="YYYY-MM-DD"),
        "Контекст": st.column_config.TextColumn("Контекст", width="large"),
    }
)

# Детальный просмотр
st.subheader("🔎 Полный контекст записи")
if not page_df.empty:
    selected_idx = st.selectbox(
        "Выберите строку для просмотра полного контекста:",
        options=page_df.index,
        format_func=lambda i: f"{page_df.loc[i, 'Имя']} — {page_df.loc[i, 'Газета']} ({page_df.loc[i, 'Дата'].date()})"
    )
    
    with st.expander("📄 Полный текст контекста", expanded=True):
        st.markdown(page_df.loc[selected_idx, "Контекст"])

# Экспорт
if st.button("📥 Экспорт отфильтрованных данных в CSV"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Скачать CSV",
        data=csv,
        file_name="упоминания_газет.csv",
        mime="text/csv"
    )