import os
import json
import requests
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin, urlparse
import argparse


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
    book_path = os.path.join(folder, sanitize_filename(filename))
    with open(book_path, "w", encoding="utf-8") as book_file:
        book_file.write(response.text)
    return book_path


def extract_book_data(soup, url):
    title_tag = soup.select_one("h1")
    title, author = title_tag.text.split(" :: ")
    img_tag = soup.select_one("div.bookimage img")
    img_url = urljoin(url, img_tag["src"]) if img_tag else None
    txt_link = soup.select_one("a:contains('скачать txt')")
    txt_url = urljoin(url, txt_link["href"]) if txt_link else None
    genres_tag = soup.select("span.d_book a")
    genres = [genre.text for genre in genres_tag] if genres_tag else []
    comments_section = soup.select("div.texts span")
    comments = [comment.text for comment in comments_section] if comments_section else []

    return {
        "title": title.strip(),
        "author": author.strip(),
        "img_url": img_url,
        "txt_url": txt_url,
        "genres": genres,
        "comments": comments
    }


def main(start_page, end_page, dest_folder='.', skip_imgs=False, skip_txt=False):
    book_data_list = []

    images_folder = os.path.join(dest_folder, 'images')
    books_folder = os.path.join(dest_folder, 'books')

    for page_number in range(start_page, end_page + 1):
        url = f'https://tululu.org/l55/{page_number}'
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        books = soup.select("div.bookimage a")

        for book in books:
            book_id = book["href"]
            book_url = urljoin(url, book_id)

            response = requests.get(book_url)
            response.raise_for_status()
            book_soup = BeautifulSoup(response.text, 'lxml')
            book_data = extract_book_data(book_soup, book_url)

            if book_data["txt_url"] and not skip_txt:
                txt_filename = f"{book_data['title']} - {book_data['author']}.txt"
                try:
                    book_data["txt_path"] = download_txt(book_data["txt_url"], {}, txt_filename, folder=books_folder)
                except requests.HTTPError:
                    print(f"Не удалось загрузить текст для {book_data['title']}")
                    continue

            if book_data["img_url"] and not skip_imgs:
                img_filename = os.path.basename(urlparse(book_data["img_url"]).path)
                try:
                    book_data["img_path"] = download_image(book_data["img_url"], img_filename, folder=images_folder)
                except requests.HTTPError:
                    print(f"Не удалось загрузить изображение для {book_data['title']}")

            book_data_list.append(book_data)

    metadata_path = os.path.join(dest_folder, "books_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as json_file:
        json.dump(book_data_list, json_file, ensure_ascii=False, indent=4)

    print(f"Загруженны данные для {len(book_data_list)} книг")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Загрузите книги и метаданные с сайта tululu.org.")
    parser.add_argument('--start_page', type=int, required=True, help="Номер начальной страницы для загрузки.")
    parser.add_argument('--end_page', type=int, required=True, help="Номер последней страницы для загрузки.")
    parser.add_argument('--dest_folder', type=str, default='.', help="Путь к каталогу для сохранения результатов.")
    parser.add_argument('--skip_imgs', action='store_true', help="Не скачивать изображения.")
    parser.add_argument('--skip_txt', action='store_true', help="Не скачивать книги.")

    args = parser.parse_args()
    main(args.start_page, args.end_page, args.dest_folder, args.skip_imgs, args.skip_txt)
