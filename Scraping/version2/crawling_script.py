"""
Product crawler for https://www.metro-markets.com/
Extracts real product data using exact selectors from the site's HTML.
Saves results as both JSON and CSV.
"""

import re
import json
import csv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# ── Config ────────────────────────────────────────────────────────────────────
START_URL         = "https://www.metro-markets.com/"
MAX_PAGES         = 30
DELAY             = 3
TIMEOUT           = 3
MAX_RETRIES       = 3
OUTPUT_FILE_JSON  = "crawl_results1.json"
OUTPUT_FILE_CSV   = "crawl_results1.csv"
HEADERS           = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

PROHIBITED_PATTERNS = [
    r'/account', r'/login', r'/recipes', r'/faqs', r'/about',
    r'/magazine', r'/register', r'/checkout', r'/cart', r'/wishlist',
    r'/order', r'/invoice', r'/profile', r'/dashboard', r'/admin',
    r'/api/internal', r'/user/', r'/my-', r'/settings', r'/payment',
    r'/shipping', r'/address', r'/tour', r'/corporate', r'/metro25',
]
# ─────────────────────────────────────────────────────────────────────────────

_PROHIBITED_RE = re.compile("|".join(PROHIBITED_PATTERNS), re.IGNORECASE)

# CSV column order
CSV_FIELDS = [
    "product_id", "name", "price", "original_price", "discount",
    "brand", "category", "availability", "description"
]


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def is_same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def is_prohibited(url: str) -> bool:
    return bool(_PROHIBITED_RE.search(urlparse(url).path))


def is_product_url(url: str) -> bool:
    return bool(re.search(r'/product/', urlparse(url).path, re.IGNORECASE))


def get_json_ld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if data.get("@type") == "Product":
                return data
        except Exception:
            pass
    return {}


def extract_product(soup: BeautifulSoup, url: str) -> dict:
    ld = get_json_ld(soup)

    # ── Name ──────────────────────────────────────────────────────────────
    name = ""
    name_el = soup.select_one(".product-details header h5")
    if name_el:
        name = name_el.get_text(strip=True)
    if not name:
        name = ld.get("name", "")
    if not name:
        og = soup.find("meta", property="og:title")
        if og:
            name = og.get("content", "")

    # ── Prices ────────────────────────────────────────────────────────────
    price = ""
    original_price = ""
    after_el  = soup.select_one(".price p.after")
    before_el = soup.select_one(".price p.before")
    if after_el:
        price = after_el.get_text(strip=True)
    if before_el:
        original_price = before_el.get_text(strip=True)
    if not price:
        offers = ld.get("offers", [{}])
        if isinstance(offers, list):
            offers = offers[0]
        p = str(offers.get("price", ""))
        c = offers.get("priceCurrency", "EGP")
        if p:
            price = f"{p} {c}"

    # ── Discount ──────────────────────────────────────────────────────────
    discount = ""
    disc_el = soup.select_one(".discound")
    if disc_el:
        discount = disc_el.get_text(strip=True)


    # ── Brand ─────────────────────────────────────────────────────────────
    brand = ld.get("brand", "")
    if not brand:
        meta_brand = soup.find("meta", property="product:brand")
        if meta_brand:
            brand = meta_brand.get("content", "")

    # ── Category ──────────────────────────────────────────────────────────
    crumbs = soup.select("ol.breadcrumb li.breadcrumb-item a")
    category = crumbs[-1].get_text(strip=True) if len(crumbs) >= 2 else ""

    # ── Availability ──────────────────────────────────────────────────────
    availability = ""
    meta_avail = soup.find("meta", property="product:availability")
    if meta_avail:
        availability = meta_avail.get("content", "")
    if not availability:
        offers = ld.get("offers", [{}])
        if isinstance(offers, list):
            offers = offers[0]
        availability = offers.get("availability", "")

    # ── Description ───────────────────────────────────────────────────────
    description = ld.get("description", "")
    if not description:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            description = meta.get("content", "")

    # ── Product ID from URL ───────────────────────────────────────────────
    match = re.search(r'/product/[^/]+/(\d+)', url)
    product_id = match.group(1) if match else ""


    return {
        "product_id":     product_id,
        "name":           name,
        "price":          price,
        "original_price": original_price,
        "discount":       discount,
        "brand":          brand,
        "category":       category,
        "availability":   availability,
        "description":    description
    }


def save_csv(products: list[dict], filepath: str) -> None:
    """Write product list to a UTF-8 CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        # utf-8-sig adds BOM so Excel opens Arabic/special chars correctly
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(products)


def crawl(start_url: str, max_pages: int = MAX_PAGES) -> dict:
    session  = build_session()
    visited  = set()
    to_visit = [start_url]
    pages    = []
    products = []
    skipped  = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)

        if url in visited:
            continue

        if is_prohibited(url):
            print(f"  ⊘ Skipped (prohibited): {url}")
            skipped.append(url)
            visited.add(url)
            continue

        print(f"[{len(visited)+1}/{max_pages}] Crawling: {url}")
        visited.add(url)

        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            print(f"  ✗ Timeout: {url}")
            pages.append({"url": url, "status": "error", "error": "Timeout"})
            continue
        except requests.RequestException as e:
            print(f"  ✗ Failed: {e}")
            pages.append({"url": url, "status": "error", "error": str(e)})
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        if is_product_url(url):
            product = extract_product(soup, url)
            product["status"] = response.status_code
            products.append(product)
            print(f"     → {product['name'] or '(no name)'} | {product['price'] or 'N/A'} → was {product['original_price'] or 'N/A'} | {product['discount']}")
        else:
            title = soup.title.get_text(strip=True) if soup.title else ""
            pages.append({"status": response.status_code, "title": title})

        for a in soup.find_all("a", href=True):
            abs_url = urljoin(url, a["href"])
            if (
                abs_url.startswith("http")
                and is_same_domain(abs_url, start_url)
                and not is_prohibited(abs_url)
                and abs_url not in visited
            ):
                to_visit.append(abs_url)

        time.sleep(DELAY)

    print(f"\n✓ Done — Products: {len(products)} | Pages: {len(pages)} | Skipped: {len(skipped)}")
    return {"products": products, "pages": pages}


def main():
    data = crawl(START_URL, MAX_PAGES)

    # ── Save JSON ──────────────────────────────────────────────────────────
    with open(OUTPUT_FILE_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"JSON saved → {OUTPUT_FILE_JSON}")

    # ── Save CSV (products only) ───────────────────────────────────────────
    save_csv(data["products"], OUTPUT_FILE_CSV)
    print(f"CSV saved  → {OUTPUT_FILE_CSV}  ({len(data['products'])} products)")


if __name__ == "__main__":
    main()