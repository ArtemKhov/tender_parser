# Тендер парсер для rostender.info

Этот проект представляет собой скрипт на Python для парсинга тендеров с сайта [https://rostender.info/extsearch](https://rostender.info/extsearch) и предоставления REST API для доступа к собранным данным.

## Возможности

- Асинхронный парсинг первых N тендеров с главной страницы поиска.
- Извлечение ключевых данных: номер, ссылка, покупатель, предмет, цена, дата окончания, местоположение.
- Сохранение данных в форматы CSV или SQLite.
- Простой CLI-интерфейс для управления скрапингом.
- FastAPI эндпоинт `/tenders` для получения данных в формате JSON.

## Использованные технологии

- **Python 3.11**
- **`httpx`**: Для асинхронных HTTP-запросов.
- **`BeautifulSoup4`**: Для парсинга HTML и извлечения данных.
- **`FastAPI`**: Для создания REST API.
- **`Uvicorn`**: ASGI сервер для запуска FastAPI приложения.
- **`SQLite3`**: Встроенная библиотека Python для работы с базой данных.

## Установка

1. **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/ArtemKhov/tender_parser.git
    cd tender_parser
    ```

2. **Создайте виртуальное окружение (рекомендуется):**
    ```bash
    python -m venv venv
   
    source venv/bin/activate # Linux/macOS
    # или
    venv\Scripts\activate # Windows
    ```

3. **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

## Использование

### 1. Парсинг тендеров (CLI)

Запустите основной скрипт `main.py`, передав нужные аргументы:

```bash
python main.py --max 100 --output tenders.csv
```

### 2. Получить данные в JSON через API
```bash
python -m uvicorn api:app --reload

Перейти по адресу: 127.0.0.1:8000/tenders
```