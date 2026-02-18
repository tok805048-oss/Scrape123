import pandas as pd
import os
import sys
from datetime import datetime
import time
import random
import re
import json
import requests
from bs4 import BeautifulSoup

# --- Konfiguracija ---
SHOP_NAME = "Slovenijales"
BASE_URL = "https://trgovina.slovenijales.si"
DDV_RATE = 0.22

# Kategorije za Slovenijales
SLOVENIJALES_CATEGORIES = {
    "LESNI MATERIALI": [
        "https://trgovina.slovenijales.si/lesni-materiali/lepljene-plosce",
        "https://trgovina.slovenijales.si/lesni-materiali/gradbene-plosce-in-les",
        "https://trgovina.slovenijales.si/lesni-materiali/opazne-plosce",
        "https://trgovina.slovenijales.si/lesni-materiali/lepljeni-nosilci",
        "https://trgovina.slovenijales.si/lesni-materiali/vezane-plosce",
        "https://trgovina.slovenijales.si/lesni-materiali/letve-palice-in-rocaji",
    ],
    "PLOSKOVNI MATERIALI": [
        "https://trgovina.slovenijales.si/ploskovni-materiali/iverne-plosce",
        "https://trgovina.slovenijales.si/ploskovni-materiali/oplemenitene-iverne-plosce",
        "https://trgovina.slovenijales.si/ploskovni-materiali/vlaknene-plosce",
        "https://trgovina.slovenijales.si/ploskovni-materiali/kuhinjski-pulti-in-obloge",
        "https://trgovina.slovenijales.si/ploskovni-materiali/kompaktne-plosce",
    ],
    "TALNE IN STENSKE OBLOGE": [
        "https://trgovina.slovenijales.si/talne-in-stenske-obloge/talne-obloge",
        "https://trgovina.slovenijales.si/talne-in-stenske-obloge/masivne-obloge",
        "https://trgovina.slovenijales.si/talne-in-stenske-obloge/zakljucni-profili-in-letve",
        "https://trgovina.slovenijales.si/talne-in-stenske-obloge/vodoodporne-stenske-obloge-rocko",
        "https://trgovina.slovenijales.si/talne-in-stenske-obloge/akusticni-paneli",
    ]
}

# --- Globalne spremenljivke ---
_log_file = None
_global_item_counter = 0

# --- Standardne pomožne funkcije ---

def log_and_print(message, to_file=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    if to_file and _log_file:
        try:
            _log_file.write(full_message + '\n')
            _log_file.flush()
        except Exception as e:
            print(f"NAPAKA: Ni mogoče zapisati v log datoteko: {e}")

def create_output_paths(shop_name):
    """Create output file paths.

    Supports OUTPUT_DIR env var (useful for GitHub Actions). Output layout:
    <OUTPUT_DIR>/Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/...
    """
    output_root = os.environ.get("OUTPUT_DIR")
    if output_root:
        main_dir = os.path.join(output_root, "Ceniki_Scraping", shop_name)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        main_dir = os.path.join(script_dir, "Ceniki_Scraping", shop_name)

    os.makedirs(main_dir, exist_ok=True)

    today_date_folder = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(main_dir, today_date_folder)
    os.makedirs(daily_dir, exist_ok=True)

    filename_date = datetime.now().strftime("%d_%m_%Y")
    json_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.json")
    excel_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.xlsx")
    log_path = os.path.join(daily_dir, f"{shop_name}_Scraping_Log_{datetime.now().strftime('%H-%M-%S')}.txt")

    print(f"JSON pot: {json_path}")
    print(f"Excel pot: {excel_path}")
    print(f"Log pot: {log_path}")
    return json_path, excel_path, log_path

def save_data(new_data, json_path, excel_path):
    if not new_data:
        log_and_print("Ni novih podatkov za shranjevanje.", to_file=True)
        return

    all_data = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except: pass
    elif os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path)
            all_data = df.to_dict(orient='records')
        except: pass

    # Ključ je URL, ker Slovenijales nima vedno šifre na seznamu
    data_dict = {item.get('URL'): item for item in all_data}
    for item in new_data:
        data_dict[item.get('URL')] = item
    
    final_list = list(data_dict.values())
    try:
        final_list.sort(key=lambda x: int(x.get('Zap', 0)))
    except: pass

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=4)
        log_and_print(f"Shranjen JSON.", to_file=True)
    except Exception as e:
        print(f"Napaka JSON: {e}")

    try:
        df = pd.DataFrame(final_list)
        cols = ["Skupina", "Zap", "Oznaka / naziv", "EAN", "Opis", "EM", "Valuta", "DDV", "Proizvajalec",
                "Veljavnost od", "Dobava", "Cena / EM (z DDV)", "Akcijska cena / EM (z DDV)",
                "Cena / EM (brez DDV)", "Akcijska cena / EM (brez DDV)", "URL", "SLIKA URL"]
        for c in cols:
            if c not in df.columns: df[c] = ''
        df[cols].to_excel(excel_path, index=False)
        log_and_print(f"Shranjen Excel.", to_file=True)
    except Exception as e:
        print(f"Napaka Excel: {e}")

def get_page_content(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        log_and_print(f"Napaka pri dostopu do URL-ja {url}: {e}", to_file=True)
        return None

def convert_price_to_without_vat(price_str, vat_rate):
    if not price_str: return ""
    try:
        cleaned = price_str.replace('.', '').replace(',', '.')
        val = float(cleaned) / (1 + vat_rate)
        return f"{val:.2f}".replace('.', ',')
    except: return ""

# --- Funkcije za Slovenijales ---

def get_product_links_from_category(category_url):
    all_links = []
    stariprvi_url = "star"
    page = 1
    while True:
        url = f"{category_url}?page={page}"
        log_and_print(f"  Stran {page}: {url}", to_file=True)
        html = get_page_content(url)
        if not html: break
        
        soup = BeautifulSoup(html, 'html.parser')
        products = soup.select('div.single-product.border-left[itemscope]')
        if not products: break

        # Preverjanje ponavljanja
        noviprvi_tag = products[0].select_one('.product-img a')
        noviprvi_url = noviprvi_tag['href'] if noviprvi_tag else None
        if page > 1 and noviprvi_url == stariprvi_url:
            log_and_print("  Vsebina se ponavlja. Konec.", to_file=True)
            break
        stariprvi_url = noviprvi_url

        for p in products:
            a = p.select_one('.product-img a')
            if a and 'href' in a.attrs:
                href = a['href']
                full = href if href.startswith('http') else BASE_URL + href
                all_links.append(full)
        
        log_and_print(f"  Najdenih {len(products)} izdelkov.", to_file=True)
        if not soup.select_one('ul.pagination a[aria-label="Naprej"]'):
            break
        page += 1
        time.sleep(random.uniform(2.0, 5.0))
    return list(set(all_links))

def get_product_details(url, cat_name, date):
    global _global_item_counter
    log_and_print(f"    - Detajli: {url}", to_file=True)
    html = get_page_content(url)
    if not html: return None
    soup = BeautifulSoup(html, 'html.parser')

    data = {"Skupina": cat_name, "Zap": 0, "Oznaka / naziv": "", "EAN": "", "Opis": "", "EM": "KOS",
            "Valuta": "EUR", "DDV": "22", "Proizvajalec": "", "Veljavnost od": date, "Dobava": "N/A",
            "Cena / EM (z DDV)": "", "Akcijska cena / EM (z DDV)": "", "URL": url, "SLIKA URL": ""}

    h1 = soup.select_one('h1[itemprop="name"]')
    if h1: data['Opis'] = h1.get_text(strip=True)

    sku = soup.select_one('meta[itemprop="sku"]')
    if sku: data['Oznaka / naziv'] = sku.get('content', '')

    ean = soup.select_one('meta[itemprop="gtin13"]')
    if ean: data['EAN'] = ean.get('content', '')

    # Cene
    new_p = soup.select_one('.product-info-price span.new')
    old_p = soup.select_one('.product-info-price span.old')
    
    if new_p:
        val = re.search(r'([\d\.,]+)', new_p.get_text(strip=True))
        if val:
            price = val.group(1).strip()
            if old_p:
                data['Akcijska cena / EM (z DDV)'] = price
                val_old = re.search(r'([\d\.,]+)', old_p.get_text(strip=True))
                if val_old: data['Cena / EM (z DDV)'] = val_old.group(1).strip()
            else:
                data['Cena / EM (z DDV)'] = price

    if not data['Opis'] and not data['Cena / EM (z DDV)']:
        return None

    _global_item_counter += 1
    data['Zap'] = _global_item_counter
    
    data['Cena / EM (brez DDV)'] = convert_price_to_without_vat(data['Cena / EM (z DDV)'], DDV_RATE)
    data['Akcijska cena / EM (brez DDV)'] = convert_price_to_without_vat(data['Akcijska cena / EM (z DDV)'], DDV_RATE)

    img = soup.select_one('.flexslider .slides img')
    if img: data['SLIKA URL'] = img.get('src', '')

    return data

def main():
    global _log_file, _global_item_counter
    time.sleep(random.uniform(0.0, 2.0) if os.environ.get("GITHUB_ACTIONS") == "true" else random.randint(1, 10))
    json_path, excel_path, log_path = create_output_paths(SHOP_NAME)
    
    try: _log_file = open(log_path, 'w', encoding='utf-8')
    except: return

    log_and_print(f"--- Zagon {SHOP_NAME} ---", to_file=True)
    
    # Naloži števec
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if d: _global_item_counter = max((int(x.get('Zap', 0)) for x in d), default=0)
            log_and_print(f"Nadaljujem z Zap: {_global_item_counter}", to_file=True)
        except: pass

    date = datetime.now().strftime("%d/%m/%Y")
    buffer = []

    try:
        for cat, urls in SLOVENIJALES_CATEGORIES.items():
            log_and_print(f"\n--- {cat} ---", to_file=True)
            for u in urls:
                links = get_product_links_from_category(u)
                for i, link in enumerate(links):
                    det = get_product_details(link, cat, date)
                    if det:
                        buffer.append(det)
                        if len(buffer) >= 5:
                            save_data(buffer, json_path, excel_path)
                            buffer = []
                    time.sleep(random.uniform(2.0, 5.0))
                if buffer:
                    save_data(buffer, json_path, excel_path)
                    buffer = []
    except Exception as e:
        log_and_print(f"NAPAKA: {e}", to_file=True)
    finally:
        save_data([], json_path, excel_path)
        if _log_file: _log_file.close()

if __name__ == "__main__":
    main()
