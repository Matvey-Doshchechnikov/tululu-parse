import os
import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlsplit, unquote
import argparse


def check_for_redirect(response):
    if response.history:
        raise requests.HTTPError("Обнаружено перенаправление")


def download_image(url, filename, folder='images/'):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, sanitize_filename(filename))
    response = requests.get(url)
    response.raise_for_status()
    check_for_redirect(response)
    with open(filepath, 'wb') as file:
        file.write(response.content)
    return filepath


def download_txt(url, filename, folder='books/'):
    os.makedirs(folder, exist_ok=True)
    try:
        response = requests.get(url)
        check_for_redirect(response)
        response.raise_for_status()
        book_path = os.path.join(folder, filename)
        with open(book_path, "w", encoding="utf-8") as book_file:
            book_file.write(response.text)
        return book_path

    except requests.HTTPError as e:
        print(f"Книга не может быть загружена: {e}")
        return None


def parse_book_page(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    title_tag = soup.find('h1')
    title_text = title_tag.text
    parts = title_text.split("::")
    book_title = parts[0].strip()
    book_author = parts[1].strip()
    image_tag = soup.find('div', class_='bookimage')
    image_url = urljoin(html_content, image_tag.find('img')['src'])
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


def main(start_id, end_id):
    for book_id in range(start_id, end_id + 1):
        book_url = f"https://tululu.org/txt.php?id={book_id}"
        page_url = f"https://tululu.org/b{book_id}/"
        try:
            response = requests.get(page_url)
            check_for_redirect(response)
            response.raise_for_status()

            book_data = parse_book_page(response.text)
            if not book_data:
                print(f"Не удалось получить данные для книги с ID {book_id}")
                continue

            filename = sanitize_filename(f"{book_data['title']}.txt")
            print(f"Загрузка книги: {filename}")
            if not download_txt(book_url, filename):
                print(f"Ошибка загрузки текста книги {book_id}")
                continue

            if book_data["image_url"]:
                image_url = urljoin(page_url, book_data["image_url"])
                image_filename = f"{book_id}.jpg"
                try:
                    download_image(image_url, image_filename)
                except requests.HTTPError as e:
                    print(f"Ошибка загрузки изображения книги {book_id}: {e}")

            print(f"Жанры: {', '.join(book_data['genres'])}")
            print(f"Комментарии: {'; '.join(book_data['comments'])}")

        except requests.HTTPError as e:
            print(f"Книга {book_id} не может быть установлена: {e}")
        except Exception as e:
            print(f"Непредвиденная ошибка для книги {book_id}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скачивание книг из tululu.org")
    parser.add_argument("start_id", type=int, help="ID книги с которой начать скачивание")
    parser.add_argument("end_id", type=int, help="ID книги до которой скачивать")
    args = parser.parse_args()

    main(args.start_id, args.end_id)
