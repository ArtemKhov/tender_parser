import pytest
from fastapi.testclient import TestClient
from api import app, DB_NAME
import sqlite3
import os
import tempfile
import shutil

# Используем TestClient для тестирования FastAPI приложения
client = TestClient(app)


# --- Фикстуры ---
@pytest.fixture(scope="function")
def temp_db():
    """Создает временную базу данных для тестов."""

    # Создаем временную директорию
    test_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(test_dir, DB_NAME)

    # Создаем тестовую таблицу и данные
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            number TEXT,
            customer TEXT,
            subject TEXT,
            price TEXT,
            end_date TEXT,
            location TEXT,
            okpd2 TEXT
        )
    ''')
    sample_data = [
        ("http://example.com/1", "T-001 01.01.2024", "Customer A", "Subject A", "1000", "01.02.2024 10:00",
         "Location A", "12.34.56"),
        ("http://example.com/2", "T-002 02.01.2024", "Customer B", "Subject B", "2000", "02.02.2024 11:00",
         "Location B", "78.90.12"),
        ("http://example.com/3", "T-003 03.01.2024", "Customer C", "Subject C", "3000", "03.02.2024 12:00",
         "Location C", "34.56.78"),
    ]
    cursor.executemany('''
        INSERT INTO tenders (url, number, customer, subject, price, end_date, location, okpd2)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_data)
    conn.commit()
    conn.close()

    # Сохраняем путь к оригинальному DB_NAME для восстановления
    original_db_name = DB_NAME

    # Патчим DB_NAME в модуле api.py, чтобы он указывал на нашу временную БД
    api_module = __import__('api', fromlist=['DB_NAME'])
    api_module.DB_NAME = test_db_path

    yield test_db_path

    # Восстанавливаем после теста
    api_module.DB_NAME = original_db_name
    # Удаляем временную директорию
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def missing_db():
    """Имитирует отсутствие базы данных."""
    original_db_name = DB_NAME
    api_module = __import__('api', fromlist=['DB_NAME'])
    # Устанавливаем путь к несуществующей БД
    api_module.DB_NAME = "non_existent_test_db.db"
    yield
    # Восстанавливаем
    api_module.DB_NAME = original_db_name


# --- Тесты ---
def test_get_tenders_default(temp_db):
    """Тест получения тендеров с параметрами по умолчанию."""
    response = client.get("/tenders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # По умолчанию limit=10, но у нас только 3 записи
    assert len(data) == 3
    # Проверяем структуру первой записи
    assert "id" in data[0]
    assert "url" in data[0]
    assert "number" in data[0]
    assert data[0]["url"] == "http://example.com/1"


def test_get_tenders_with_limit_and_offset(temp_db):
    """Тест получения тендеров с limit и offset."""
    response = client.get("/tenders?limit=2&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Проверяем, что это правильные записи (со смещением 1)
    assert data[0]["url"] == "http://example.com/2"
    assert data[1]["url"] == "http://example.com/3"


def test_get_tenders_empty_result(temp_db):
    """Тест получения тендеров с offset за пределами данных."""
    response = client.get("/tenders?offset=100")
    assert response.status_code == 200
    data = response.json()
    assert data == []  # Должен вернуть пустой список


def test_get_tenders_db_not_found(missing_db):
    """Тест получения тендеров, когда БД отсутствует."""
    response = client.get("/tenders")
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "не найдена" in data["detail"]