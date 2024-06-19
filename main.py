import os
import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlencode
import argparse
import time


MAX_RETRIES = 3


class BookParsingError(Exception):
    pass


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError("Обнаружено перенаправление")


def download_image(url, filename, folder='images/'):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, sanitize_filename(filename))
    response = requests.get(url)
    check_for_redirect(response)
    response.raise_for_status()
    with open(filepath, 'wb') as file:
        file.write(response.content)
    return filepath


def download_txt(url, payload, filename, folder='books/'):
    os.makedirs(folder, exist_ok=True)
    response = requests.get(url, params=payload)
    check_for_redirect(response)
    response.raise_for_status()
    book_path = os.path.join(folder, filename)
    with open(book_path, "w", encoding="utf-8") as book_file:
        book_file.write(response.text)
    return book_path


def parse_book_page(html_content, base_url):
    soup = BeautifulSoup(html_content, 'lxml')
    title_tag = soup.find('h1')
    if not title_tag:
        raise BookParsingError("Тег заголовка не найден")

    title_text = title_tag.text
    parts = title_text.split("::")
    if len(parts) < 2:
        raise BookParsingError("Название не содержит автора")

    book_title = parts[0].strip()
    book_author = parts[1].strip()

    image_tag = soup.find('div', class_='bookimage')
    if not image_tag:
        raise BookParsingError("Тег изображения не найден")

    image_url = urljoin(base_url, image_tag.find('img')['src'])

    comments_tag = soup.find_all('div', class_='texts')
    comments = [comment_tag.find('span', class_='black').text for comment_tag in comments_tag]

    genre_tags = soup.find('span', class_='d_book').find_all("a")
    genres = [tag.text for tag in genre_tags]

    return {
        "title": book_title,
        "author": book_author,
        "image_url": image_url,
        "comments": comments,
        "genres": genres
    }


def download_books(book_id):
    payload = {'id': book_id}
    base_url = "https://tululu.org/txt.php"
    page_url = f"https://tululu.org/b{book_id}/"

    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            response = requests.get(page_url)
            check_for_redirect(response)
            response.raise_for_status()
            break
        except requests.HTTPError as e:
            print(f"Не удалось получить страницу книги с ID {book_id}: {e}")
            break
        except requests.RequestException as e:
            print(f"Ошибка запроса для книги с ID {book_id}: {e}")
        except ConnectionError as e:
            print(f"Ошибка соединения: {e}")

        retry_count += 1
        print(f"Повторная попытка через 5 секунд...")
        time.sleep(5)

    if retry_count == MAX_RETRIES:
        print(f"Не удалось получить страницу книги с ID {book_id} после {MAX_RETRIES} попыток.")
        return

    try:
        book_details = parse_book_page(response.text, page_url)
    except BookParsingError as e:
        print(f"Ошибка парсинга данных книги с ID {book_id}: {e}")
        return

    filename = sanitize_filename(f"{book_details['title']}.txt")
    print(f"Загрузка книги: {filename}")

    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            download_txt(base_url, payload, filename)
            break
        except requests.HTTPError as e:
            print(f"Ошибка загрузки текста книги с ID {book_id}: {e}")
        except requests.RequestException as e:
            print(f"Ошибка запроса для текста книги с ID {book_id}: {e}")
        except IOError as e:
            print(f"Ошибка записи файла для книги с ID {book_id}: {e}")

        retry_count += 1
        print(f"Повторная попытка через 5 секунд...")
        time.sleep(5)

    if book_details["image_url"]:
        image_url = book_details["image_url"]
        image_filename = f"{book_id}.jpg"
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                download_image(image_url, image_filename)
                break
            except requests.HTTPError as e:
                print(f"Ошибка загрузки изображения книги с ID {book_id}: {e}")
            except requests.RequestException as e:
                print(f"Ошибка запроса для изображения книги с ID {book_id}: {e}")
            except IOError as e:
                print(f"Ошибка записи изображения для книги с ID {book_id}: {e}")

            retry_count += 1
            print(f"Повторная попытка через 5 секунд...")
            time.sleep(5)

        if retry_count == MAX_RETRIES:
            print(f"Не удалось загрузить изображение книги с ID {book_id} после {MAX_RETRIES} попыток.")

    print(f"Жанры: {', '.join(book_details['genres'])}")
    print(f"Комментарии: {'; '.join(book_details['comments'])}")


def main():
    parser = argparse.ArgumentParser(description="Скачивание книг из tululu.org")
    parser.add_argument("start_id", type=int, help="ID книги с которой начать скачивание")
    parser.add_argument("end_id", type=int, help="ID книги до которой скачивать")
    args = parser.parse_args()

    for book_id in range(args.start_id, args.end_id + 1):
        download_books(book_id)


if __name__ == "__main__":
    main()
