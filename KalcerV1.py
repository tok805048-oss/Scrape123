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
SHOP_NAME = "Kalcer"
BASE_URL = "https://www.trgovina-kalcer.si"
DDV_RATE = 0.22

# Celoten seznam kategorij iz vaše datoteke
KALCER_CATEGORIES = {
    'Gradnja': [
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadne-izolacije',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadna-lepila-in-malte',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadne-barve-in-zakljucni-sloji',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadna-sidra',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadne-mrezice-in-profili',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/fasadni-izdelki/fasadne-stukature',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/toplotne-izolacije/steklena-izolacija',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/toplotne-izolacije/kamena-izolacija',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/toplotne-izolacije/izolacijske-plosce',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/toplotne-izolacije/izolacijska-folija',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/toplotne-izolacije/izolacijsko-nasutje',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/folije-za-izolacijo',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/izolacijski-lepilni-trakovi',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/izolacijska-tesnila',
        'https://www.trgovina-kalcer.si/gradnja/izolacije/pozarni-izdelki-plosce',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/gradbene-plosce-gradnja',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/konstrukcija',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/pribor-za-suhi-estrih',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/suhi-estrihi',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/podlage-za-suhi-estrih',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/ogrevanje-hlajenje/talno-ogrevanje-hlajenje',
        'https://www.trgovina-kalcer.si/gradnja/suhomontazni-sistemi/ogrevanje-hlajenje/stensko-in-stropno-ogrevanje-hlajenje',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/svetila',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/pripomocki-pritrjevanje-suha-gradnja',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/fugiranje-armiranje/mase',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/fugiranje-armiranje/trakovi',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/fugiranje-armiranje/vogalniki',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/revizijske-odprtine',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/ciscenje',
        'https://www.trgovina-kalcer.si/gradnja/pripomocki-suha-gradnja/barvanje',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/hidroizolacije/stresne-folije',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/hidroizolacije/tekoce-brezsivne-folije',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/hidroizolacije/bitumenske-hidroizolacije',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/hidroizolacije/cementne-hidroizolacije',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/izravnalne-mase',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/radonska-zascita',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/tesnilne-mase',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/tesnilni-trakovi',
        'https://www.trgovina-kalcer.si/gradnja/lepljenje-tesnenje/lepila',
        'https://www.trgovina-kalcer.si/gradnja/gradbena-akustika/zvocni-absorberji',
        'https://www.trgovina-kalcer.si/gradnja/gradbena-akustika/zvocne-izolacije',
        'https://www.trgovina-kalcer.si/gradnja/gradbena-akustika/modularni-stropi',
        'https://www.trgovina-kalcer.si/gradnja/gradbena-akustika/akusticni-pribor'
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
    """Create output file paths.

    Supports OUTPUT_DIR env var (useful for GitHub Actions). Output structure:
      <OUTPUT_DIR>/Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/
    If OUTPUT_DIR is not set, defaults to the directory of this script.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.environ.get("OUTPUT_DIR") or script_dir

    today_date_folder = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(output_root, "Ceniki_Scraping", shop_name, today_date_folder)
    os.makedirs(daily_dir, exist_ok=True)

    filename_date = datetime.now().strftime("%d_%m_%Y")
    json_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.json")
    excel_path = os.path.join(daily_dir, f"{shop_name}_Podatki_{filename_date}.xlsx")
    log_path = os.path.join(daily_dir, f"{shop_name}_Scraping_Log_{datetime.now().strftime('%H-%M-%S')}.txt")
    return json_path, excel_path, log_path

def save_data(new_data, json_path, excel_path):
    if not new_data: return
    all_data = []
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f: all_data = json.load(f)
        except: pass
    elif os.path.exists(excel_path):
        try:
            df = pd.read_excel(excel_path)
            all_data = df.to_dict(orient='records')
        except: pass

    data_dict = {item.get('URL'): item for item in all_data}
    for item in new_data:
        data_dict[item.get('URL')] = item
    
    final_list = list(data_dict.values())
    try: final_list.sort(key=lambda x: int(x.get('Zap', 0)))
    except: pass

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=4)
        log_and_print(f"Shranjen JSON.", to_file=True)
    except: pass

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
        url = f"{category_url}&page={page}"
        log_and_print(f"  Stran {page}: {url}", to_file=True)
        html = get_page_content(url)
        if not html: break
        
        soup = BeautifulSoup(html, 'html.parser')
        products = soup.select('.product-list > div, .product-grid .product')
        if not products: break
        
        for item in products:
            a = item.select_one('.name a')
            if a and a.get('href'): all_links.append(a['href'])

        text = soup.select_one('.pagination-results .text-right')
        if not text or "Prikazujem" not in text.get_text(): break
        
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

    h1 = soup.select_one('h1.product-name')
    if not h1: h1 = soup.select_one('h1.productInfo')
    if h1: data['Opis'] = h1.get_text(strip=True)

    rows = soup.select('.listing.stockMargin tr')
    for row in rows:
        cells = row.select('td')
        if len(cells) == 2:
            k = cells[0].get_text(strip=True)
            v = cells[1].get_text(strip=True)
            if 'Ident' in k: data['Oznaka / naziv'] = v
            elif 'Enota mere' in k: data['EM'] = v

    brand = soup.select_one('.product-info .description a[href*="/m-"]')
    if brand: data['Proizvajalec'] = brand.get_text(strip=True)

    p = soup.select_one('span.productSpecialPrice')
    if not p: p = soup.select_one('.price-new, .price')
    
    if p:
        m = re.search(r'([\d\.,]+)', p.get_text(strip=True))
        if m: data['Cena / EM (z DDV)'] = m.group(1).strip()

    data['Cena / EM (brez DDV)'] = convert_price_to_without_vat(data['Cena / EM (z DDV)'], DDV_RATE)
    
    img = soup.select_one('a.lightbox-image')
    if img and img.get('href'): data['SLIKA URL'] = img['href']

    return data

def main():
    global _log_file, _global_item_counter
    time.sleep(random.randint(0, 2) if os.environ.get('GITHUB_ACTIONS') else random.randint(1, 10))
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
        for cat, urls in KALCER_CATEGORIES.items():
            log_and_print(f"\n--- {cat} ---", to_file=True)
            for u in urls:
                sub_name = u.split('/')[-1]
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