import csv
import json
import re
import time
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


START_URLS = [
    "https://www.metro-markets.com/categoryl1/Bakery/9",
    "https://www.metro-markets.com/categoryl1/Beverage/22",
    "https://www.metro-markets.com/categoryl1/Canned-Food/14",
    "https://www.metro-markets.com/categoryl1/Confectionary/20",
    "https://www.metro-markets.com/categoryl1/Dairy/6",
    "https://www.metro-markets.com/categoryl1/Deli/5",
    "https://www.metro-markets.com/categoryl1/Eatery/2",
    "https://www.metro-markets.com/categoryl1/Fresh-Juices/8",
    "https://www.metro-markets.com/categoryl1/Frozen-Food/10",
    "https://www.metro-markets.com/categoryl1/Fruit/1",
    "https://www.metro-markets.com/categoryl1/Commodities/15",
    "https://www.metro-markets.com/categoryl1/Health&-Beauty/28",
    "https://www.metro-markets.com/categoryl1/Home-Bake/16",
    "https://www.metro-markets.com/categoryl1/Home-Base/4",
    "https://www.metro-markets.com/categoryl1/Home-&Fabric-Care/26",
    "https://www.metro-markets.com/categoryl1/Hot-Drinks/21",
    "https://www.metro-markets.com/categoryl1/Metro/39"
    ]
OUTPUT_CSV = "metro_products.csv"
OUTPUT_JSON = "metro_products.json"
MAX_PAGES = 30  # Safety limit
DELAY_MS = 5000  # 5 seconds
GOTO_TIMEOUT_MS = 60000  # 60 seconds for page navigation


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def first_text(card, selectors):
    for sel in selectors:
        el = card.query_selector(sel)
        if el:
            t = clean_text(el.inner_text())
            if t:
                return t
    return ""


def first_attr(card, selectors, attr):
    for sel in selectors:
        el = card.query_selector(sel)
        if el:
            v = (el.get_attribute(attr) or "").strip()
            if v:
                return v
    return ""


def parse_price(text: str):
    t = clean_text(text)
    m = re.search(r"(\d+[.,]?\d*)", t)
    if not m:
        return None
    return m.group(1).replace(",", ".")


def extract_products_from_page(page):
    card_selectors = [
        ".product-item",
        ".product-card",
        ".item-product",
        "[data-product-id]",
        ".products .item",
        ".product",
    ]

    cards = []
    for sel in card_selectors:
        cards = page.query_selector_all(sel)
        if cards:
            break

    products = []
    for card in cards:
        name = first_text(
            card,
            [
                ".product-name",
                ".name",
                "h2",
                "h3",
                "a[title]",
                ".product-title",
            ],
        )
        if not name:
            name = first_attr(card, ["a[title]", ".product-name a", "h3 a"], "title")

        url = first_attr(card, ["a[href]", ".product-name a[href]", "h3 a[href]"], "href")
        image = first_attr(card, ["img", ".product-image img"], "src") or first_attr(
            card, ["img", ".product-image img"], "data-src"
        )

        price_text = first_text(
            card,
            [".price", ".special-price", ".regular-price", ".amount", "[class*='price']"],
        )
        old_price_text = first_text(card, [".old-price", ".was-price", ".price-old"])

        product = {
            "name": name,
            "url": urljoin(page.url, url) if url else "",
            "price_text": price_text,
            "price": parse_price(price_text) if price_text else None,
            "old_price_text": old_price_text,
            "old_price": parse_price(old_price_text) if old_price_text else None,
            "image": urljoin(page.url, image) if image else "",
            "source_page": page.url,
        }

        # Keep only likely valid product entries
        if product["name"] or product["url"]:
            products.append(product)

    return products


def click_load_more_if_present(page):
    selectors = [
        "button:has-text('Load more')",
        "button:has-text('Show more')",
        "a:has-text('Load more')",
        "a:has-text('Show more')",
        ".load-more",
    ]
    for sel in selectors:
        btn = page.query_selector(sel)
        if btn and btn.is_visible():
            try:
                btn.click(timeout=DELAY_MS)
                page.wait_for_timeout(DELAY_MS)
                return True
            except Exception:
                pass
    return False


def find_next_page_url(page):
    selectors = [
        "a[rel='next']",
        "a.next",
        ".pagination a.next",
        "a:has-text('Next')",
        "a[aria-label='Next']",
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            href = (el.get_attribute("href") or "").strip()
            if href:
                return urljoin(page.url, href)
    return None

def dedupe_products(products):
    seen = set()
    out = []
    for p in products:
        key = p.get("url") or p.get("name")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def save_csv(products, path):
    fields = ["name", "url", "price_text", "price", "old_price_text", "old_price", "image", "source_page"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(products)


def save_json(products, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def run():
    all_products = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()

        for start_url in START_URLS:
            print(f"\n--- Scraping from: {start_url} ---")
            visited_pages = set()
            next_url = start_url
            page_count = 0

            while next_url and page_count < MAX_PAGES:
                if next_url in visited_pages:
                    break
                visited_pages.add(next_url)
                page_count += 1

                print(f"[{page_count}] Visiting: {next_url}")
                try:
                    page.goto(next_url, wait_until="load", timeout=GOTO_TIMEOUT_MS)
                    print(f"  ✓ Page loaded successfully")
                except Exception as e:
                    print(f"  ✗ Error loading page: {type(e).__name__}: {str(e)[:100]}")
                    try:
                        next_url = find_next_page_url(page)
                    except Exception:
                        next_url = None
                    continue
                
                page.wait_for_timeout(DELAY_MS)

                # Handle infinite/lazy loading
                for _ in range(5):
                    page.mouse.wheel(0, 5000)
                    page.wait_for_timeout(DELAY_MS)
                    if not click_load_more_if_present(page):
                        break

                try:
                    products = extract_products_from_page(page)
                    print(f"  ✓ Found {len(products)} products on page")
                    all_products.extend(products)
                except Exception as e:
                    print(f"  ✗ Error extracting products: {type(e).__name__}: {str(e)[:100]}")

                try:
                    next_url = find_next_page_url(page)
                    if next_url:
                        print(f"  ✓ Next page found: {next_url}")
                    else:
                        print(f"  ✓ No more pages")
                except Exception as e:
                    print(f"  ✗ Error finding next page: {type(e).__name__}: {str(e)[:100]}")
                    next_url = None

        browser.close()

    all_products = dedupe_products(all_products)
    save_csv(all_products, OUTPUT_CSV)
    save_json(all_products, OUTPUT_JSON)
    print(f"\nSaved {len(all_products)} unique products")
    print(f"- {OUTPUT_CSV}")
    print(f"- {OUTPUT_JSON}")


if __name__ == "__main__":
    run()
