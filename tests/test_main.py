import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from main import (
    extract_tender_links_from_page,
    parse_tender_details,
    save_to_csv,
    save_to_sqlite,
    RUSSIAN_TO_ENGLISH_KEYS
)
from bs4 import BeautifulSoup
import tempfile
import os
import sqlite3
import csv

# --- HTML-фикстуры для тестов ---

HTML_SEARCH_PAGE = """
<html>
<body>
    <div class="tender-info">
        <h2><a href="/tender/123">Тендер 1</a></h2>
    </div>
    <div class="tender-info">
        <a href="/tender/456">Тендер 2</a>
    </div>
    <div class="pagination">
        <a href="?page=2">Следующая</a>
    </div>
</body>
</html>
"""

HTML_TENDER_PAGE = """
<html>
<body>
    <div class="tender-info-header-number">T-999</div>
    <div class="tender-info-header-start_date">01.04.2024</div>

    <div>Покупатель</div>
    <div class="customer-name">Госзакупки РФ</div>

    <h1 data-id="name">Поставка бумаги</h1>

    <span>Начальная цена</span>
    <span class="tender-body__field">50 000 руб.</span>

    <span>Окончание</span>
    <div class="tender-body__block">
        <span class="tender-body__field">
            <span class="black">10.04.2024</span>
            <span class="tender__countdown-container">15:00 (МСК)</span>
        </span>
    </div>

    <div data-id="place">Москва</div>

    <div>ОКПД2</div>
    <div>18.20.10</div>
</body>
</html>
"""


# --- Тесты ---

def test_save_to_csv():
    """Тест сохранения данных в CSV файл."""
    test_data = [
        {
            "Ссылка": "http://test1.com",
            "Номер и дата создания тендера": "T-1",
            "Покупатель": "Покупатель 1",
            "Предмет тендера": "Предмет 1",
            "Цена": "100",
            "Окончание (МСК)": "01.01.2025",
            "Место поставки": "Город 1",
            "okpd2": "01.01.01"
        },
        {
            "Ссылка": "http://test2.com",
            "Номер и дата создания тендера": "T-2",
            "Покупатель": "Покупатель 2",
            "Предмет тендера": "Предмет 2",
            "Цена": "200",
            "Окончание (МСК)": "02.01.2025",
            "Место поставки": "Город 2",
            "okpd2": "02.02.02"
        }
    ]

    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w', newline='', encoding='utf-8') as tmpfile:
        tmp_filename = tmpfile.name

    try:
        save_to_csv(test_data, tmp_filename)

        # Проверяем содержимое файла
        with open(tmp_filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["Ссылка"] == "http://test1.com"
        assert rows[1]["Покупатель"] == "Покупатель 2"

    finally:
        os.remove(tmp_filename)


def test_save_to_sqlite():
    """Тест сохранения данных в SQLite базу данных."""
    test_data = [
        {
            "Ссылка": "http://test1.com",
            "Номер и дата создания тендера": "T-1",
            "Покупатель": "Покупатель 1",
            "Предмет тендера": "Предмет 1",
            "Цена": "100",
            "Окончание (МСК)": "01.01.2025",
            "Место поставки": "Город 1",
            "okpd2": "01.01.01"
        }
    ]

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmpfile:
        tmp_db_name = tmpfile.name

    try:
        save_to_sqlite(test_data, tmp_db_name)

        # Проверяем содержимое БД
        conn = sqlite3.connect(tmp_db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tenders")
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 1
        row_dict = dict(rows[0])

        # Проверяем, что ключи переведены
        assert "url" in row_dict
        assert "customer" in row_dict
        assert row_dict["url"] == "http://test1.com"
        assert row_dict["customer"] == "Покупатель 1"

    finally:
        os.remove(tmp_db_name)