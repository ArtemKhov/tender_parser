import argparse
import csv
import sqlite3
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import asyncio
import logging


# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Константы ---
BASE_URL = "https://rostender.info"
SEARCH_URL = f"{BASE_URL}/extsearch"
MAX_RETRIES = 5
RETRY_DELAY = 2


# --- Перевод полей с ru на en для безошибочного формирования DB ---
RUSSIAN_TO_ENGLISH_KEYS = {
    "Ссылка": "url",
    "Номер и дата создания тендера": "number",
    "Покупатель": "customer",
    "Предмет тендера": "subject",
    "Цена": "price",
    "Окончание (МСК)": "end_date",
    "Место поставки": "location",
    "okpd2": "okpd2"
}


async def fetch_page_content(client: httpx.AsyncClient, url: str) -> Optional[BeautifulSoup]:
    """Асинхронно загружает содержимое страницы."""
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning(f"Ошибка при загрузке {url} (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"Не удалось загрузить {url} после {MAX_RETRIES} попыток.")
    return None


def extract_tender_links_from_page(soup: BeautifulSoup) -> List[str]:
    """Извлекает ссылки на страницы отдельных тендеров с одной страницы результатов."""
    links = []
    tender_items = soup.find_all('div', class_='tender-info')

    if not tender_items:
        # Альтернативная попытка найти ссылки
        all_links = soup.find_all('a', href=True)
        tender_links = [a['href'] for a in all_links if '/tender/' in a['href']]
        # Удаляем дубликаты, сохраняя порядок
        seen = set()
        unique_links = []
        for link in tender_links:
            # Нормализуем URL
            full_url = urljoin(BASE_URL, link) if not link.startswith('http') else link
            if full_url not in seen:
                seen.add(full_url)
                unique_links.append(full_url)
        return unique_links

    for item in tender_items:
        link_tag = item.find('a', href=True)
        if not link_tag:
             # Пробуем найти заголовок с ссылкой
             header = item.find('h2') or item.find('h3') or item.find('h4')
             if header:
                 link_tag = header.find('a', href=True)

        if link_tag:
            full_url = urljoin(BASE_URL, link_tag['href'])
            links.append(full_url)
    return links


async def parse_tender_list(client: httpx.AsyncClient, max_tenders: int) -> List[str]:
    """Извлекает ссылки на страницы отдельных тендеров из страниц поиска с пагинацией."""
    all_links = []
    current_page = 1
    base_params = {}

    logger.info(f"Начинаем сбор ссылок на тендеры. Цель: {max_tenders} тендеров.")

    while len(all_links) < max_tenders:
        if current_page == 1:
            url = SEARCH_URL
        else:
            parsed_url = urlparse(SEARCH_URL)
            query_params = parse_qs(parsed_url.query)
            query_params['page'] = [str(current_page)]
            query_string = urlencode(query_params, doseq=True)
            url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{query_string}"

        logger.info(f"Загрузка страницы результатов поиска: {url}")
        search_soup = await fetch_page_content(client, url)

        if not search_soup:
            logger.error(f"Не удалось загрузить страницу поиска {url}. Останавливаем сбор ссылок.")
            break

        # Извлекаем ссылки с текущей страницы
        page_links = extract_tender_links_from_page(search_soup)
        logger.info(f"Найдено {len(page_links)} ссылок на странице {current_page}.")

        if not page_links:
            logger.info("На странице не найдено ссылок на тендеры. Возможно, это последняя страница.")
            break

        # Добавляем новые ссылки, соблюдая лимит
        for link in page_links:
            if len(all_links) >= max_tenders:
                break
            if link not in all_links:
                all_links.append(link)

        logger.info(f"Всего ссылок собрано: {len(all_links)} из {max_tenders} требуемых.")


        if len(all_links) >= max_tenders:
            break
        current_page += 1

        # Небольшая задержка между запросами страниц
        await asyncio.sleep(0.5)

    logger.info(f"Сбор ссылок завершен. Всего собрано: {len(all_links)} ссылок.")
    return all_links[:max_tenders] # На всякий случай обрезаем до точного количества


def parse_tender_details(soup: BeautifulSoup, tender_url: str) -> Dict:
    """Извлекает детали конкретного тендера."""
    data = {
        "Ссылка": tender_url,
        "Номер и дата создания тендера": "N/A",
        "Покупатель": "N/A",
        "Предмет тендера": "N/A",
        "Цена": "N/A",
        "Окончание (МСК)": "N/A",
        "Место поставки": "N/A",
        "okpd2": "N/A"
    }

    try:
        # Номер тендера
        number_elem = soup.find('div', class_='tender-info-header-number')
        if number_elem:
            number_text = number_elem.get_text(strip=True)

            date_elem = soup.find('div', class_='tender-info-header-start_date')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                data['Номер и дата создания тендера'] = f"{number_text} {date_text}"
            else:
                # Если дата не найдена, сохраняем только номер
                if any(char.isdigit() for char in number_text):
                    data['Номер и дата создания тендера'] = number_text

        # Покупатель
        customer_elem = soup.find('div', string=lambda text: text and 'Покупатель' in text)
        if customer_elem:
            next_elem = customer_elem.find_next('div') or customer_elem.find_next('span')
            if next_elem:
                data['Покупатель'] = next_elem.get_text(strip=True)
        # Альтернативный способ поиска покупателя, если структура другая
        if data['Покупатель'] == "N/A":
            customer_elem_alt = soup.find('div', class_='customer-name')
            if customer_elem_alt:
                data['Покупатель'] = customer_elem_alt.get_text(strip=True)

        # Предмет тендера
        subject_elem = soup.select_one('h1[data-id="name"]')
        if subject_elem:
            data['Предмет тендера'] = subject_elem.get_text(strip=True)

        # Если название тендера все еще N/A, попробуем другие способы
        if data['Предмет тендера'] == "N/A":
            # Ищем по другим возможным селекторам
            alternative_subject = soup.find('h1', class_='tender-header__h4')
            if alternative_subject:
                data['Предмет тендера'] = alternative_subject.get_text(strip=True)

        # Поиск цены
        price_label = soup.find('span', string=lambda text: text and 'Начальная цена' in text)
        if price_label:
            price_span = price_label.find_next_sibling('span', class_='tender-body__field')
            if price_span:
                data['Цена'] = price_span.get_text(strip=True)

        # Поиск даты окончания подачи заявок
        end_date_label = soup.find('span', string=lambda text: text and 'Окончание' in text)
        if end_date_label:
            parent_div = end_date_label.find_parent('div', class_='tender-body__block')
            if parent_div:
                date_field = parent_div.find('span', class_='tender-body__field')
                if date_field:
                    date_span = date_field.find('span', class_='black')
                    date_text = date_span.get_text(strip=True) if date_span else ''

                    time_span = date_field.find('span', class_='tender__countdown-container')
                    time_text = time_span.get_text(strip=True) if time_span else ''

                    # Собираем результат с пробелом между датой и временем
                    if date_text and time_text:
                        data['Окончание (МСК)'] = f"{date_text} {time_text}"
                    elif date_text:
                        data['Окончание (МСК)'] = date_text


        # Местоположение
        if data['Место поставки'] == "N/A":
            location_elem_alt = soup.find('div', {'data-id': 'place'})
            if location_elem_alt:
                location_text = location_elem_alt.get_text(strip=True)
                if location_text:
                    data['Место поставки'] = location_text

        # Код ОКПД2
        okpd2_elem = soup.find('div', string=lambda text: text and 'ОКПД2' in text)
        if okpd2_elem:
            next_elem = okpd2_elem.find_next('div') or okpd2_elem.find_next('span')
            if next_elem:
                data['okpd2'] = next_elem.get_text(strip=True)

    except Exception as e:
        logger.error(f"Ошибка при парсинге деталей тендера {tender_url}: {e}")

    return data


def save_to_csv(data: List[Dict], filename: str):
    """Сохраняет данные в CSV файл."""
    if not data:
        logger.warning("Нет данных для сохранения в CSV.")
        return
    if data:
        fieldnames = list(data[0].keys())
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        if set(fieldnames) != all_keys:
             logger.warning("Найдены расхождения в ключах словарей. Используются ключи первого элемента.")

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"Данные сохранены в {filename}")


def save_to_sqlite(data: List[Dict], db_name: str = "tenders.db"):
    """Сохраняет данные в SQLite базу данных."""
    if not data:
        logger.warning("Нет данных для сохранения в SQLite.")
        return

    # Определяем английские ключи для колонок
    english_keys = list(RUSSIAN_TO_ENGLISH_KEYS.values())

    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Создаем таблицу с английскими именами колонок
    columns_def = ", ".join([f"{key} TEXT" for key in english_keys])
    create_table_sql = f'''
        CREATE TABLE IF NOT EXISTS tenders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {columns_def}
        )
    '''
    cursor.execute(create_table_sql)

    for item in data:
        english_item = {}
        for ru_key, en_key in RUSSIAN_TO_ENGLISH_KEYS.items():
            english_item[en_key] = item.get(ru_key, "N/A")

        values = [english_item[key] for key in english_keys]

        placeholders = ', '.join(['?' for _ in english_keys])
        columns_str = ', '.join(english_keys)

        insert_sql = f'''
            INSERT OR REPLACE INTO tenders ({columns_str})
            VALUES ({placeholders})
        '''
        try:
            cursor.execute(insert_sql, values)
        except sqlite3.Error as e:
            logger.error(f"Ошибка при вставке данных в SQLite: {e}. Данные: {english_item}")

    conn.commit()
    conn.close()
    logger.info(f"Данные сохранены в базу данных {db_name}")

async def scrape_tenders(max_tenders: int, output_file: str):
    """Основная асинхронная функция для скрапинга."""
    logger.info(f"Начинаем скрапинг. Цель: {max_tenders} тендеров.")
    tenders_data = []

    async with httpx.AsyncClient(base_url=BASE_URL, follow_redirects=True) as client:
        # 1. Извлечь ссылки на тендеры с пагинацией
        logger.info("Извлечение ссылок на тендеры...")
        tender_links = await parse_tender_list(client, max_tenders)
        logger.info(f"Всего найдено {len(tender_links)} уникальных ссылок на тендеры.")

        # 2. Для каждой ссылки загрузить страницу и извлечь данные
        logger.info("Начинаем парсинг деталей тендеров...")
        for i, link in enumerate(tender_links):
            logger.info(f"Парсинг тендера {i + 1}/{len(tender_links)}: {link}")
            tender_soup = await fetch_page_content(client, link)
            if tender_soup:
                tender_data = parse_tender_details(tender_soup, link)
                tenders_data.append(tender_data)
            else:
                logger.warning(f"Пропущен тендер {link} из-за ошибки загрузки.")
            # Добавляем небольшую задержку, чтобы не перегружать сервер
            await asyncio.sleep(0.5)

    # 3. Сохранить данные
    if output_file.endswith('.csv'):
        save_to_csv(tenders_data, output_file)
    elif output_file.endswith('.db') or output_file.endswith('.sqlite'):
        save_to_sqlite(tenders_data, output_file)
    else:
        # По умолчанию сохраняем в CSV
        save_to_csv(tenders_data, output_file)
        logger.info("Формат файла не распознан, данные сохранены в CSV.")

# --- CLI ---
def main():
    parser = argparse.ArgumentParser(description="Скрипт для парсинга тендеров с rostender.info")
    parser.add_argument('--max', type=int, default=100,
                        help='Максимальное количество тендеров для загрузки (по умолчанию 10)')
    parser.add_argument('--output', type=str, default='tenders.csv',
                        help='Имя выходного файла (CSV или SQLite .db/.sqlite)')

    args = parser.parse_args()

    asyncio.run(scrape_tenders(args.max, args.output))

if __name__ == '__main__':
    main()