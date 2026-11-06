"""Parse the observed KVKK news cards; stop on unexpected source changes."""
import logging
import time
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scripts.models import Announcement, SOURCE_URL, content_id, normalize_url, parse_date


class SourceError(RuntimeError):
    pass


def parse_page(html: str, page: int = 1):
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("section.news")
    if section is None:
        raise SourceError("Duyuru liste konteyneri bulunamadı; şablon değişmiş olabilir")
    cards = section.select(".news__box")
    if not cards:
        # Do not infer end-of-list from missing cards. Pagination decides when to stop.
        raise SourceError(f"Sayfa {page}: sıfır duyuru; mevcut yayın korunacak")
    items = []
    invalid = 0
    for card in cards:
        try:
            meta = card.select_one(".news__box-meta")
            if meta is None:
                raise ValueError("Kart metaverisi yok")
            anchor = meta.select_one("a[href]")
            date_node = meta.select_one(".date")
            if anchor is None or date_node is None:
                raise ValueError("Başlık / tarih yok")
            url = normalize_url(anchor["href"])
            title = " ".join(anchor.get_text(" ", strip=True).split())
            # Container is the primary selector; wording only assists diagnostics.
            if "ihlali" not in title.casefold().replace("\u0307", ""):
                logging.warning("Beklenmedik duyuru başlığı: %s", title)
            items.append(Announcement(content_id(url), title, url,
                                      parse_date(date_node.get_text(" ", strip=True))))
        except (ValueError, TypeError) as exc:
            invalid += 1
            logging.warning("Sayfa %d: hatalı kayıt atlandı: %s", page, exc)
    if not items or invalid / len(cards) > 0.2:
        raise SourceError(f"Sayfa {page}: çok fazla geçersiz duyuru ({invalid}/{len(cards)})")
    pages = set()
    for link in section.select(".pagination a[href]"):
        target = urlsplit(urljoin(SOURCE_URL, link["href"]))
        if target.hostname != "www.kvkk.gov.tr" or target.path.rstrip("/") != "/veri-ihlali-bildirimi":
            continue
        value = parse_qs(target.query).get("page", [""])[0]
        if value.isdigit():
            pages.add(int(value))
    return items, pages


class Scraper:
    def __init__(self, source_url=SOURCE_URL, timeout=15, delay=1, user_agent="kvkk-rss/1.0", session=None):
        self.source_url = normalize_url(source_url)
        if urlsplit(self.source_url).path != "/veri-ihlali-bildirimi":
            raise ValueError("Kaynak, KVKK veri ihlali liste adresi olmalı")
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, url):
        # Redirects are intentionally disallowed; never follow a source to another host.
        response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            raise SourceError(f"Beklenmedik yönlendirme: {url}")
        response.encoding = "utf-8"
        return response

    def check_robots(self):
        url = "https://www.kvkk.gov.tr/robots.txt"
        response = self.session.get(url, timeout=self.timeout, allow_redirects=False)
        # Observed robots.txt redirects to the homepage: no robots rules are served.
        if response.status_code in {404, 410} or (
            response.status_code in {301, 302, 303, 307, 308} and
            response.headers.get("Location", "") in {"/", "https://www.kvkk.gov.tr/"}
        ):
            logging.info("robots.txt sunulmuyor (HTTP %s)", response.status_code)
            return
        response.raise_for_status()
        if response.status_code != 200 or "<html" in response.text.lower():
            raise SourceError("robots.txt yanıtı doğrulanamadı")
        robots = RobotFileParser()
        robots.parse(response.text.splitlines())
        if not robots.can_fetch(self.user_agent, self.source_url):
            raise SourceError("robots.txt liste taramasına izin vermiyor")
        crawl_delay = robots.crawl_delay(self.user_agent)
        if crawl_delay is not None:
            self.delay = max(self.delay, crawl_delay)

    def collect(self, max_pages=5):
        self.check_robots()
        found = {}
        for page in range(1, max_pages + 1):
            time.sleep(self.delay)
            url = self.source_url if page == 1 else f"{self.source_url}?page={page}"
            items, pages = parse_page(self.get(url).text, page)
            page_ids = {item.id for item in items}
            if page > 1 and page_ids <= found.keys():
                raise SourceError("Sayfalama aynı kayıtları tekrar döndürdü")
            for item in items:
                if item.id in found:
                    logging.warning("Sayfalar arasında yinelenen kimlik: %s", item.id)
                    if found[item.id] != item:
                        raise SourceError(f"Çelişen yinelenen kayıt: {item.id}")
                found[item.id] = item
            logging.info("Sayfa %d: %d duyuru", page, len(items))
            if not pages:
                if page == 1 and max_pages > 1:
                    raise SourceError("Sayfalama bulunamadı; eksik tarama riski")
                break
            if not any(number > page for number in pages):
                break
        return list(found.values())
