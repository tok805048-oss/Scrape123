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
SHOP_NAME = "OBI"
BASE_URL = "https://www.obi.si"
DDV_RATE = 0.22

# Kategorije za OBI
OBI_CATEGORIES = {
    "Ploščice": [
        "https://www.obi.si/c/gradnja-877/ploscice-308/talne-ploscice-1150",
        "https://www.obi.si/c/gradnja-877/ploscice-308/stenske-ploscice-786",
        "https://www.obi.si/c/gradnja-877/ploscice-308/stenske-obrobe-1850",
        "https://www.obi.si/c/gradnja-877/ploscice-308/okrasne-ploscice-1849",
        "https://www.obi.si/c/gradnja-877/ploscice-308/ploscice-iz-naravnega-kamna-1151",
        "https://www.obi.si/c/gradnja-877/ploscice-308/obzidniki-in-koticki-481",
        "https://www.obi.si/c/gradnja-877/ploscice-308/mozaiki-572",
        "https://www.obi.si/c/gradnja-877/ploscice-308/robne-ploscice-1152"
    ],
    "Ureditev okolice": [
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/pohodne-plosce-914",
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/tlakovci-608",
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/obrobe-stopnice-in-zidni-sistemi-1281",
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/terasne-deske-1464",
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/terasne-in-pohodne-plosce-1279",
        "https://www.obi.si/c/gradnja-877/ureditev-okolice-336/okrasni-prod-in-okrasni-drobljenec-1382"
    ],
    "Gradbeni materiali": [
        "https://www.obi.si/c/gradnja-877/gradbeni-materiali-175/omet-malta-in-cement-619",
        "https://www.obi.si/c/gradnja-877/gradbeni-materiali-175/suha-gradnja-764",
        "https://www.obi.si/c/gradnja-877/gradbeni-materiali-175/kamni-in-pesek-720",
        "https://www.obi.si/c/gradnja-877/gradbeni-materiali-175/izolacijski-material-233"
    ]
}

_log_file = None
_global_item_counter = 0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

def log_and_print(message, to_file=True):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    if to_file and _log_file:
        try:
            _log_file.write(full_message + '\n')
            _log_file.flush()
        except Exception as e:
            print(f"Log Error: {e}")

def create_output_paths(shop_name):
    """Ustvari poti za JSON/Excel in log.

    GitHub/CI:
      - če je nastavljen env OUTPUT_DIR, se vse piše pod to mapo (npr. artifacts/)
      - drugače se piše ob skripti
    Struktura:
      OUTPUT_ROOT/Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.environ.get("OUTPUT_DIR", script_dir)

    today_date_folder = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(output_root, "Ceniki_Scraping", shop_name, today_date_folder)
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
    if not new_data: return
    all_data = []
    
    # 1. Naloži obstoječe (JSON prednostno)
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

    # 2. Združi (ključ je URL)
    data_dict = {item.get('URL'): item for item in all_data}
    for item in new_data:
        data_dict[item.get('URL')] = item
    
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
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        log_and_print(f"Error {url}: {e}", to_file=True)
        return None

def convert_price_to_without_vat(price_str, vat_rate):
    if not price_str: return ""
    try:
        cleaned = price_str.replace('.', '').replace(',', '.')
        val = float(cleaned) / (1 + vat_rate)
        return f"{val:.2f}".replace('.', ',')
    except: return ""

def main():
    global _log_file, _global_item_counter
    # Naključen zamik za varnost
    time.sleep(random.uniform(0, 2) if os.environ.get("GITHUB_ACTIONS","").lower()=="true" else random.randint(1, 10))
    
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
        except: pass

    date = datetime.now().strftime("%d/%m/%Y")
    buffer = []

    try:
        for cat, urls in OBI_CATEGORIES.items():
            log_and_print(f"--- {cat} ---", to_file=True)
            for u in urls:
                sub_name = u.strip('/').split('/')[-1]
                log_and_print(f"  Podkategorija: {sub_name}", to_file=True)
                
                n = 1
                stariprvi = "star"
                
                while True:
                    p_url = f"{u}?p={n}"
                    log_and_print(f"    Stran {n}: {p_url}", to_file=True)
                    html = get_page_content(p_url)
                    if not html: break
                    
                    soup = BeautifulSoup(html, 'lxml')
                    container = soup.find("div", class_="list-items list-category-products")
                    if not container: break
                    
                    items = container.find_all("div", class_="item")
                    if not items: break
                    
                    # Preverjanje ponavljanja (OBI včasih vrti isto stran)
                    noviprvi = items[0].h4.text if items[0].h4 else None
                    if n > 1 and noviprvi == stariprvi:
                        log_and_print("    Stran se ponavlja. Konec kategorije.", to_file=True)
                        break
                    stariprvi = noviprvi

                    for i in items:
                        a = i.find("a")
                        if not a: continue
                        url = a.get("href")
                        
                        _global_item_counter += 1
                        data = {"Skupina": cat, "Zap": _global_item_counter, "Veljavnost od": date,
                                "Valuta": "EUR", "DDV": "22", "EM": "kos", "URL": url}

                        # Pridobi ceno takoj iz seznama (hitreje)
                        price_span = i.find("span", class_="price")
                        if price_span:
                            c = re.findall(r'[\d\.,]+', price_span.text)
                            if c: data['Cena / EM (z DDV)'] = c[0]
                            
                            # Poskus pridobitve EM iz teksta (npr. "€/m2")
                            try:
                                unit_text = re.search(r'\s*/\s*(.*)$', price_span.parent.text.strip()).group(1)
                                data['EM'] = unit_text
                            except: pass

                        data['Cena / EM (brez DDV)'] = convert_price_to_without_vat(data.get('Cena / EM (z DDV)'), DDV_RATE)
                        
                        img = i.find("img")
                        data['SLIKA URL'] = img.get("src") if img else ''
                        
                        # Dodatni detajli (Opis, Šifra)
                        time.sleep(random.uniform(1.0, 2.0)) # OBI zahteva počasnejši tempo
                        d_html = get_page_content(url)
                        if d_html:
                            s2 = BeautifulSoup(d_html, "html.parser")
                            info = s2.find("div", class_="product-basics-info part-1")
                            data['Opis'] = info.h1.text.strip() if info and info.h1 else ''
                            sid = s2.find("div", class_="product-id")
                            data['Oznaka / naziv'] = sid.text.strip() if sid else ''
                        
                        buffer.append(data)
                        if len(buffer) >= 5:
                            save_data(buffer, json_path, excel_path)
                            buffer = []

                    if not soup.select_one('a.next'): break
                    n += 1

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