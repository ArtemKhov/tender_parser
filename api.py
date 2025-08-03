from fastapi import FastAPI, HTTPException
import sqlite3
import os

app = FastAPI(title="Tender Scraper API", description="API для получения данных о тендерах")

DB_NAME = "tenders.db"


@app.get("/tenders", summary="Получить список тендеров")
async def get_tenders(limit: int = 10, offset: int = 0):
    """
    Возвращает список тендеров из базы данных SQLite.
    - **limit**: Максимальное количество тендеров (по умолчанию 10).
    - **offset**: Смещение для пагинации (по умолчанию 0).
    """
    if not os.path.exists(DB_NAME):
        raise HTTPException(status_code=500, detail=f"База данных {DB_NAME} не найдена. Сначала запустите скрапинг.")

    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tenders LIMIT ? OFFSET ?", (limit, offset))
        rows = cursor.fetchall()

        tenders = [dict(row) for row in rows]

        conn.close()
        return tenders
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка работы с базой данных: {e}")

# Для запуска: python -m uvicorn api:app --reload