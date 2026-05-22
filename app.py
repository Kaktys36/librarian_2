import os
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Просмотр базы упоминаний", layout="wide")
st.title("Просмотр базы данных упоминаний")

DB_PATH = "newspapers.db"  # лежит рядом с app.py


@st.cache_data(ttl=300)
def inspect_db():
    """Проверяем наличие файла и таблиц, возвращаем список таблиц."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Файл базы данных не найден: {os.path.abspath(DB_PATH)}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    conn.close()
    return [t[0] for t in tables]


@st.cache_data(ttl=300)
def load_data():
    """Читаем данные из newspaper_mentions, если таблица есть."""
    conn = sqlite3.connect(DB_PATH)
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
    return df_local


# ---- сначала посмотрим, что внутри БД ----
try:
    table_names = inspect_db()
except Exception as e:
    st.error(f"Ошибка при проверке БД: {e}")
    st.stop()

st.sidebar.markdown(f"**Файл БД:** `{os.path.abspath(DB_PATH)}`")
st.sidebar.markdown(f"**Таблицы в БД:** {table_names}")

if "newspaper_mentions" not in table_names:
    st.error(
        "В базе данных нет таблицы `newspaper_mentions`.\n\n"
        f"Найдены таблицы: {table_names}\n\n"
        "Проверьте, что вы загрузили правильный файл `newspapers.db`."
    )
    st.stop()

# ---- теперь пробуем загрузить данные из newspaper_mentions ----
try:
    df = load_data()
except Exception as e:
    st.error(f"Ошибка при чтении таблицы `newspaper_mentions`: {e}")
    st.stop()

if df.empty:
    st.error("Таблица `newspaper_mentions` пуста.")
    st.stop()

# ==================== БОКОВАЯ ПАНЕЛЬ ====================
st.sidebar.header("Фильтры")

# Фильтр по имени
name_filter = st.sidebar.text_input("Поиск по имени человека", "")
if name_filter:
    df = df[df["Имя"].astype(str).str.contains(name_filter, case=False, na=False)]

# Фильтр по газете
gazeta_series = df["Газета"].astype(str).str.strip()
gazeta_series = gazeta_series[gazeta_series != ""]
newspaper_list = sorted(list(set(gazeta_series.tolist())))

selected_newspapers = st.sidebar.multiselect(
    "Газета",
    options=newspaper_list,
    default=newspaper_list,
    help="Можно выбрать несколько",
)

if selected_newspapers:
    df = df[df["Газета"].astype(str).str.strip().isin(selected_newspapers)]

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
