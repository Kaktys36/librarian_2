import os
import re
import sqlite3
import pymupdf

DB_PATH = "newspapers.db"
PDF_FOLDER = "newspapers"

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_newspaper_name_from_pdf(pdf_path: str) -> str:
    try:
        doc = pymupdf.open(pdf_path)
        full_text = ""
        for page_num in range(min(4, len(doc))):   # первые 4 страницы
            full_text += doc[page_num].get_text("text")
        doc.close()

        text = clean_text(full_text.upper())

        if "ПРАВДА КОММУНИЗМА" in text:
            if "РЕЖЕВСКОГО ГОРОДСКОГО КОМИТЕТА" in text or "ОРГАН РЕЖЕВСКОГО" in text:
                return "Правда Коммунизма (орган Режевского ГК КПСС)"
            return "Правда Коммунизма"
        
        if "РЕЖЕВСКАЯ ПРАВДА" in text:
            return "Режевская правда"

        # Если ничего не нашли — ищем первую строку с заглавными буквами
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        for line in lines[:20]:
            if any(k in line.upper() for k in ["ПРАВДА", "РЕЖЕВ", "ГАЗЕТА"]):
                cleaned = re.sub(r'[^А-Яа-яЁё\s-]', '', line).strip()
                if len(cleaned) > 5:
                    return cleaned.title()

        return "Правда Коммунизма"

    except Exception as e:
        print(f"❌ Ошибка чтения {os.path.basename(pdf_path)}: {e}")
        return "Правда Коммунизма"


def fix_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Добавляем колонку pdf_filename, если её нет
    cursor.execute("PRAGMA table_info(newspaper_mentions)")
    if "pdf_filename" not in [col[1] for col in cursor.fetchall()]:
        cursor.execute("ALTER TABLE newspaper_mentions ADD COLUMN pdf_filename TEXT")

    cursor.execute("SELECT id, pdf_filename FROM newspaper_mentions")
    rows = cursor.fetchall()

    updated = 0
    for row_id, pdf_filename in rows:
        if not pdf_filename:
            continue
            
        pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
        if not os.path.exists(pdf_path):
            continue

        correct_name = extract_newspaper_name_from_pdf(pdf_path)
        
        cursor.execute("""
            UPDATE newspaper_mentions 
            SET newspaper_name = ? 
            WHERE id = ?
        """, (correct_name, row_id))
        updated += 1

    conn.commit()
    conn.close()
    print(f"\n✅ Обновлено записей: {updated}")


if __name__ == "__main__":
    print("🔧 Запуск точного исправления названий газет...\n")
    fix_database()

    # Показываем результат
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT newspaper_name, COUNT(*) as cnt 
        FROM newspaper_mentions 
        GROUP BY newspaper_name 
        ORDER BY cnt DESC
    """)
    print("\nРезультат после исправления:")
    for name, count in cursor.fetchall():
        print(f"   • {name:<45} — {count} записей")
    conn.close()