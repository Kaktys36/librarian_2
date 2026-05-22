import os
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Просмотр базы упоминаний", layout="wide")
st.title("Просмотр базы данных упоминаний")

DB_PATH = "newspapers.db"  # файл лежит рядом с app.py


def open_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Файл базы данных не найден: {os.path.abspath(DB_PATH)}")
    return sqlite3.connect(DB_PATH)


@st.cache_data(ttl=300)
def load_data_single_connection():
    conn = open_connection()
    cur = conn.cursor()

    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    table_names = [t[0] for t in tables]

    if "newspaper_mentions" not in table_names:
        conn.close()
        raise RuntimeError(
            f"В БД {os.path.abspath(DB_PATH)} нет таблицы 'newspaper_mentions'. "
            f"Найдены таблицы: {table_names}"
        )

    sample = cur.execute(
        "SELECT id, newspaper_name, publication_date, person_name, context, pdf_filename "
        "FROM newspaper_mentions LIMIT 5;"
    ).fetchall()

    try:
        df_local = pd.read_sql_query(
            """
            SELECT 
                id,
                newspaper_name AS Газета,
                publication_date AS Дата,
                person_name AS Имя,
                context AS Контекст,
                pdf_filename AS Файл
            FROM newspaper_mentions
            ORDER BY publication_date, newspaper_name, person_name
            """,
            conn,
        )
    finally:
        conn.close()

    return df_local, table_names, sample


# ---- загрузка ----
try:
    df, table_names, sample_rows = load_data_single_connection()
except Exception as e:
    size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    st.error(
        f"Ошибка при работе с БД.\n\n"
        f"Файл: {os.path.abspath(DB_PATH)} (размер: {size} байт)\n\n"
        f"Ошибка: {e}"
    )
    st.stop()

size = os.path.getsize(DB_PATH)
st.sidebar.markdown(f"**Файл БД:** `{os.path.abspath(DB_PATH)}`")
st.sidebar.markdown(f"**Размер файла:** {size} байт")
st.sidebar.markdown(f"**Таблицы в БД:** {table_names}")
st.sidebar.markdown(f"**Первые 5 строк (сырой запрос):** {sample_rows}")

if df.empty:
    st.error("Таблица `newspaper_mentions` пуста.")
    st.stop()

# ==================== БОКОВАЯ ПАНЕЛЬ ====================
st.sidebar.header("Фильтры")

# Фильтр по имени
name_filter = st.sidebar.text_input("Поиск по имени человека", "")
if name_filter:
    df = df[df["Имя"].astype(str).str.contains(name_filter, case=False, na=False)]

# ======== ФИЛЬТР ПО ГАЗЕТЕ (без tolist/set/unique) ========
# Берём значения, убираем NaN и пустые строки, всё переводим в str
gazeta_values = df["Газета"].dropna()
gazeta_values = gazeta_values[gazeta_values.astype(str).str.strip() != ""]
# pd.unique возвращает массив, дальше просто sorted(map(str, ...))
newspaper_list = sorted(map(str, pd.unique(gazeta_values)))

selected_newspapers = st.sidebar.multiselect(
    "Газета",
    options=newspaper_list,
    default=newspaper_list,
    help="Можно выбрать несколько",
)

if selected_newspapers:
    df = df[df["Газета"].astype(str).isin(selected_newspapers)]

# Фильтр по дате
df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")

if df["Дата"].notna().any():
    min_date = df["Дата"].min().date()
    max_date = df["Дата"].max().date()

    date_range = st.sidebar.date_input(
        "Диапазон дат",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        df = df[
            (df["Дата"].dt.date >= start_date)
            & (df["Дата"].dt.date <= end_date)
        ]
else:
    st.sidebar.warning("Не удалось распознать даты, фильтр по дате отключён.")

st.sidebar.markdown(f"**Найдено записей:** {len(df)}")

# ==================== ТАБЛИЦА ====================
st.subheader(f"📋 Список упоминаний ({len(df)} записей)")

page_size = st.selectbox("Записей на странице", [20, 50, 100, 200], index=0)
max_page = max(1, (len(df) - 1) // page_size + 1)
page_num = st.number_input("Страница", min_value=1, max_value=max_page, value=1, step=1)

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
    },
)

# Детальный просмотр
st.subheader("Полный контекст записи")
if not page_df.empty:
    selected_idx = st.selectbox(
        "Выберите строку для просмотра полного контекста:",
        options=page_df.index,
        format_func=lambda i: f"{page_df.loc[i, 'Имя']} — {page_df.loc[i, 'Газета']} ({page_df.loc[i, 'Дата'].date()})",
    )

    with st.expander("Полный текст контекста", expanded=True):
        st.markdown(page_df.loc[selected_idx, "Контекст"])

# Экспорт
if st.button("Экспорт отфильтрованных данных в CSV"):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Скачать CSV",
        data=csv,
        file_name="упоминания_газет.csv",
        mime="text/csv",
    )
