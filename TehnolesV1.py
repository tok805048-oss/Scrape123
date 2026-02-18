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
SHOP_NAME = "Tehnoles"
BASE_URL = "https://www.tehnoles.si"
DDV_RATE = 0.22

# Kategorije za Tehnoles
TEHNOLES_CATEGORIES = {
    "Gradbeni material": [
        "https://www.tehnoles.si/gradbeni-material-c-28.aspx",
        "https://www.tehnoles.si/barve-laki-in-premazi-c-31.aspx",
        "https://www.tehnoles.si/lepila-in-kiti-c-32.aspx",
        "https://www.tehnoles.si/izolacije-c-48.aspx",
        "https://www.tehnoles.si/suhomontazni-material-c-17.aspx",
        "https://www.tehnoles.si/kasetni-stropi-c-84.aspx",
        "https://www.tehnoles.si/delovna-zascitna-sredstva-c-69.aspx",
        "https://www.tehnoles.si/delovni-stroji-c-160.aspx",
        "https://www.tehnoles.si/vodovod-c-151.aspx"
    ],
    "Orodje": [
        "https://www.tehnoles.si/rocno-orodje-c-41.aspx",
        "https://www.tehnoles.si/elektricno-orodje-c-40.aspx"
    ]
}

_log_file = None
_global_item_counter = 0

def log_and_print(message, to_file=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    if to_file and _log_file:
        try:
            _log_file.write(full_message + '\n')
            _log_file.flush()
        except: pass

def create_output_paths(shop_name):
    """Create output paths.
    Supports OUTPUT_DIR env var (useful for GitHub Actions).
    Output structure:
      <OUTPUT_DIR>/Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/...
    If OUTPUT_DIR is not set, writes next to this script.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.environ.get("OUTPUT_DIR")
    today_date_folder = datetime.now().strftime("%Y-%m-%d")
    filename_date = datetime.now().strftime("%d_%m_%Y")

    if output_root:
        daily_dir = os.path.join(output_root, "Ceniki_Scraping", shop_name, today_date_folder)
    else:
        daily_dir = os.path.join(script_dir, "Ceniki_Scraping", shop_name, today_date_folder)

    os.makedirs(daily_dir, exist_ok=True)

    json_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.json")
    excel_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.xlsx")
    log_path = os.path.join(daily_dir, f"{shop_name}_Scraping_Log_{datetime.now().strftime('%H-%M-%S')}.txt")
    return json_path, excel_path, log_path

def save_data(new_data, json_path, excel_path):
    if not new_data: return
    all_data = []
    
    # 1. Naloži obstoječe (JSON prednostno)
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f: all_data = json.load(f)
        except: pass
    elif os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path)
            all_data = df.to_dict(orient='records')
        except: pass

    # 2. Združi
    data_dict = {item.get('URL'): item for item in all_data}
    for item in new_data: data_dict[item.get('URL')] = item
    
    final_list = list(data_dict.values())
    try: final_list.sort(key=lambda x: int(x.get('Zap', 0)))
    except: pass

    # 3. Shrani JSON
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=4)
        log_and_print(f"Shranjen JSON.", to_file=True)
    except: pass

    # 4. Shrani Excel
    try:
        df = pd.DataFrame(final_list)
        cols = ["Skupina", "Zap", "Oznaka / naziv", "EAN", "Opis", "EM", "Valuta", "DDV", "Proizvajalec",
                "Veljavnost od", "Dobava", "Cena / EM (z DDV)", "Akcijska cena / EM (z DDV)",
                "Cena / EM (brez DDV)", "Akcijska cena / EM (brez DDV)", "URL", "SLIKA URL"]
        for c in cols:
            if c not in df.columns: df[c] = ''
        df[cols].to_excel(excel_path, index=False)
        log_and_print(f"Shranjen Excel.", to_file=True)
    except: pass

def get_page_content(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except: return None

def convert_price_to_without_vat(price_str, vat_rate):
    if not price_str: return ""
    try:
        cleaned = price_str.replace('.', '').replace(',', '.')
        val = float(cleaned) / (1 + vat_rate)
        return f"{val:.2f}".replace('.', ',')
    except: return ""

def get_product_links_from_category(category_url):
    all_links = []
    page = 1
    while True:
        url = f"{category_url}?pagenum={page}"
        log_and_print(f"  Stran {page}: {url}", to_file=True)
        html = get_page_content(url)
        if not html: break
        
        soup = BeautifulSoup(html, 'html.parser')
        products = soup.select('li.wrapper_prods.category')
        if not products: break
        
        for item in products:
            a = item.select_one('.name a')
            if a and a.get('href'):
                full = BASE_URL + a['href']
                all_links.append(full)
        
        if not soup.select_one('a.PagerPrevNextLink'): break
        page += 1
        time.sleep(random.uniform(2.0, 5.0))
    return list(set(all_links))

def get_product_details(url, cat, date):
    global _global_item_counter
    log_and_print(f"    - Detajli: {url}", to_file=True)
    html = get_page_content(url)
    if not html: return None
    soup = BeautifulSoup(html, 'html.parser')

    _global_item_counter += 1
    data = {"Skupina": cat, "Zap": _global_item_counter, "Veljavnost od": date, "Valuta": "EUR", "DDV": "22",
            "URL": url, "SLIKA URL": "", "Opis": "", "Oznaka / naziv": "", "EM": "KOS", "Cena / EM (z DDV)": ""}

    h1 = soup.select_one('h1.productInfo')
    if h1: data['Opis'] = h1.get_text(strip=True)

    rows = soup.select('.listing.stockMargin tr')
    for row in rows:
        cells = row.select('td')
        if len(cells) == 2:
            k = cells[0].get_text(strip=True)
            v = cells[1].get_text(strip=True)
            if 'Ident' in k: data['Oznaka / naziv'] = v
            elif 'Enota mere' in k: data['EM'] = v

    p = soup.select_one('span.productSpecialPrice')
    if not p: p = soup.select_one('span.priceColor')
    
    if p:
        m = re.search(r'([\d\.,]+)', p.get_text(strip=True))
        if m: data['Cena / EM (z DDV)'] = m.group(1).strip()

    data['Cena / EM (brez DDV)'] = convert_price_to_without_vat(data['Cena / EM (z DDV)'], DDV_RATE)
    
    img = soup.select_one('a.lightbox-image')
    if img and img.get('href'): data['SLIKA URL'] = BASE_URL + img['href']

    return data

def main():
    global _log_file, _global_item_counter
    # Keep a small jitter locally; on GitHub Actions avoid wasting minutes.
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or os.environ.get("CI"):
        time.sleep(random.uniform(0.2, 1.0))
    else:
        time.sleep(random.randint(1, 10))
    json_path, excel_path, log_path = create_output_paths(SHOP_NAME)
    try: _log_file = open(log_path, 'w', encoding='utf-8')
    except: return
    log_and_print(f"--- Zagon {SHOP_NAME} ---", to_file=True)

    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if d: _global_item_counter = max((int(x.get('Zap', 0)) for x in d), default=0)
        except: pass

    date = datetime.now().strftime("%d/%m/%Y")
    buffer = []

    try:
        for cat, urls in TEHNOLES_CATEGORIES.items():
            log_and_print(f"\n--- {cat} ---", to_file=True)
            for u in urls:
                # Izluščimo ime podkategorije iz URL-ja
                sub_name = u.split('/')[-1].split('-c-')[0]
                links = get_product_links_from_category(u)
                
                for link in links:
                    det = get_product_details(link, sub_name, date)
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
