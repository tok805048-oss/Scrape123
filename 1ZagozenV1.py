import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import random
import os
import sys
import json
from datetime import datetime

# --- Konfiguracija ---
SHOP_NAME = "Zagozen"
BASE_URL = "https://eshop-zagozen.si/"
DDV_RATE = 0.22  # Stopnja DDV (22%)

CATEGORIES = {
    "vodovod": [
        "zbiralniki-za-vodo-aquastay-in-oprema",
        "vodomerni-termo-jaski-in-oprema",
        "vodovodne-pe-cevi-in-spojke",
        "spojke-za-popravila",
        "pocinkani-fitingi-protipovratni-in-krogelni-ventili",
        "hisni-prikljucki-za-vodovod",
        "ventili-za-redukcijo-tlaka",
        "ploscata-tesnila",
        "dodatno"
    ],
    "kanalizacija": [
        "kanalizacijske-cevi-in-fazoni",
        "kanalizacijski-jaski-in-oprema",
        "lovilci-olj-in-mascob",
        "cistilne-naprave-in-oprema",
        "ponikovalna-polja",
        "drenazne-cevi",
        "greznice",
        "kanalizacijski-pokrovi-resetke-in-oprema",
        "opozorilni-trakovi",
        "crpalni-jaski"
    ],
    "zascita-in-energetika": [
        "pe-cevi-za-zascito-aflex-in-spojke",
        "pvc-energetske-cevi",
        "opozorilni-trakovi"
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
    """Create output paths in a CI-friendly way.

    If OUTPUT_DIR env var is set (e.g. in GitHub Actions), all outputs go under:
      OUTPUT_DIR/Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/

    Otherwise outputs are written next to this script (local dev).
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
    return json_path, excel_path, log_path


def save_data(new_data, json_path, excel_path):
    if not new_data:
        log_and_print("Ni novih podatkov za shranjevanje.", to_file=True)
        return

    all_data = []

    # 1. Naloži obstoječe (JSON prednostno)
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except Exception as e:
            print(f"Napaka pri branju JSON: {e}")
    elif os.path.exists(excel_path):
        try:
            df_existing = pd.read_excel(excel_path)
            all_data = df_existing.to_dict(orient='records')
        except Exception as e:
            print(f"Napaka pri branju Excel: {e}")

    # 2. Združevanje in odstranjevanje duplikatov
    # Za Zagožen je ključ "Oznaka / naziv" (šifra artikla)
    def make_key(item):
        oznaka = str(item.get('Oznaka / naziv', '')).strip()
        if oznaka:
            return f"ID_{oznaka}"
        return f"URL_{item.get('URL')}"

    data_dict = {make_key(item): item for item in all_data}
    
    for item in new_data:
        key = make_key(item)
        data_dict[key] = item

    final_list = list(data_dict.values())

    # 3. Uredi po Zap
    try:
        final_list.sort(key=lambda x: int(x.get('Zap', 0)))
    except:
        pass

    # 4. SHRANI JSON
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, ensure_ascii=False, indent=4)
        log_and_print(f"Shranjeno v JSON: {json_path}", to_file=True)
    except Exception as e:
        log_and_print(f"Napaka pri shranjevanju JSON: {e}", to_file=True)

    # 5. SHRANI EXCEL
    try:
        df = pd.DataFrame(final_list)
        desired_columns = [
            "Skupina", "Zap", "Oznaka / naziv", "EAN", "Opis", "EM", "Valuta", "DDV",
            "Proizvajalec", "Veljavnost od", "Dobava",
            "Cena / EM (z DDV)", "Akcijska cena / EM (z DDV)",
            "Cena / EM (brez DDV)", "Akcijska cena / EM (brez DDV)",
            "URL", "SLIKA URL"
        ]
        
        for col in desired_columns:
            if col not in df.columns:
                df[col] = ''
        
        df = df[desired_columns]
        df.to_excel(excel_path, index=False)
        log_and_print(f"Shranjeno v Excel: {excel_path}", to_file=True)
    except Exception as e:
        log_and_print(f"Napaka pri shranjevanju Excel: {e}", to_file=True)


def get_page_content(url):
    headers = {
        'User-Agent': random.choice([
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
        ])
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        log_and_print(f"Napaka pri dostopu do URL-ja {url}: {e}", to_file=True)
        return None


def get_product_links_from_subcategory(category_slug, subcategory_slug):
    all_product_links = []
    page = 1
    
    log_and_print(f"\n--- Zajemanje iz: {subcategory_slug} ---", to_file=True)

    while True:
        if page == 1:
            url = f"{BASE_URL}{category_slug}/{subcategory_slug}"
        else:
            url = f"{BASE_URL}{category_slug}/{subcategory_slug}?p={page}"

        log_and_print(f"  Preverjam stran {page}: {url}", to_file=True)
        html_content = get_page_content(url)
        if not html_content: break

        soup = BeautifulSoup(html_content, 'html.parser')

        # Preveri, če ni izdelkov
        no_products = soup.find('p', class_='note-msg')
        if no_products and "ni izdelkov" in no_products.get_text().lower():
            break

        product_grid = soup.find('ul', class_='products-grid')
        if not product_grid: break

        product_items = product_grid.find_all('li', class_='item')
        if not product_items: break

        for li in product_items:
            link_tag = li.find('a', class_='product-image')
            if link_tag and 'href' in link_tag.attrs:
                all_product_links.append(link_tag['href'])

        log_and_print(f"  Najdenih {len(product_items)} izdelkov na strani {page}.", to_file=True)

        # Naslednja stran
        next_page = soup.select_one('div.pages a.next, div.pages a.i-next')
        if not next_page: break

        page += 1
        time.sleep(random.uniform(2.0, 5.0))

    return all_product_links


def convert_price_with_vat_to_without_vat(price_str, vat_rate):
    if not price_str: return ""
    try:
        cleaned = price_str.replace('.', '').replace(',', '.')
        val = float(cleaned)
        val_no_vat = val / (1 + vat_rate)
        return f"{val_no_vat:.2f}".replace('.', ',')
    except:
        return ""


def clean_price_string(price_str):
    if not price_str: return ""
    return price_str.replace('€', '').replace('\xa0', '').replace('.', '').strip()


def get_product_details(product_url, category_name, subcategory_name, query_date):
    global _global_item_counter
    log_and_print(f"  - Zajemanje podrobnosti za: {product_url}", to_file=True)

    html_content = get_page_content(product_url)
    if not html_content: return None

    soup = BeautifulSoup(html_content, 'html.parser')

    product_data = {
        "Skupina": category_name, "Zap": "", "Oznaka / naziv": "", "EAN": "",
        "Opis": "", "EM": "KOS", "Valuta": "EUR", "DDV": "22",
        "Proizvajalec": "", "Veljavnost od": query_date, "Dobava": "",
        "Cena / EM (z DDV)": "", "Akcijska cena / EM (z DDV)": "",
        "Cena / EM (brez DDV)": "", "Akcijska cena / EM (brez DDV)": "",
        "URL": product_url, "SLIKA URL": ""
    }

    # Opis
    name_tag = soup.find('div', class_='product-name')
    if name_tag and name_tag.h1:
        product_data["Opis"] = name_tag.h1.get_text(strip=True)

    # SKU / Šifra
    sku_div = soup.find('div', class_='sku')
    if sku_div:
        sifra_strong = sku_div.find('strong')
        if sifra_strong:
            product_data["Oznaka / naziv"] = sifra_strong.get_text(strip=True)
        
        # Dobava
        dobava_span = sku_div.find('span', class_='dobava')
        if dobava_span:
            product_data["Dobava"] = dobava_span.get_text(strip=True).replace('Dobava:', '').strip()

    _global_item_counter += 1
    product_data["Zap"] = _global_item_counter

    # Cene
    price_box = soup.find('div', class_='price-box')
    if price_box:
        special_p = price_box.find('p', class_='special-price')
        old_p = price_box.find('p', class_='old-price')
        regular_span = price_box.find('span', class_='regular-price')

        if special_p:
            # Akcija
            p_val = special_p.find('span', class_='price')
            if p_val: product_data["Akcijska cena / EM (z DDV)"] = clean_price_string(p_val.get_text(strip=True))
            
            if old_p:
                p_old = old_p.find('span', class_='price')
                if p_old: product_data["Cena / EM (z DDV)"] = clean_price_string(p_old.get_text(strip=True))
        elif regular_span:
            # Redna
            p_val = regular_span.find('span', class_='price')
            if p_val: product_data["Cena / EM (z DDV)"] = clean_price_string(p_val.get_text(strip=True))

    # Izračun brez DDV
    product_data["Cena / EM (brez DDV)"] = convert_price_with_vat_to_without_vat(product_data["Cena / EM (z DDV)"], DDV_RATE)
    product_data["Akcijska cena / EM (brez DDV)"] = convert_price_with_vat_to_without_vat(product_data["Akcijska cena / EM (z DDV)"], DDV_RATE)

    # EM
    em_div = soup.find('div', class_='em')
    if em_div:
        em_text = em_div.get_text(strip=True)
        # Iščemo tekst za "Cena je na"
        match = re.search(r'Cena je na\s*([^\.]+)', em_text, re.IGNORECASE)
        if match:
            product_data["EM"] = match.group(1).strip().upper()

    # Slika
    img = soup.select_one('.product-img-box img#image-main, .product-img-box img.gallery-image')
    if img: product_data["SLIKA URL"] = img.get('src', '')

    return product_data


# --- Glavna funkcija ---

def main():
    global _log_file, _global_item_counter
    
    # Avoid wasting GitHub Actions minutes on long random startup sleeps
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        time.sleep(random.uniform(0.0, 2.0))
    else:
        time.sleep(random.randint(1, 10))
    json_path, excel_path, log_path = create_output_paths(SHOP_NAME)

    try:
        _log_file = open(log_path, 'w', encoding='utf-8')
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return

    log_and_print(f"--- Zagon {SHOP_NAME} ---", to_file=True)

    # Naloži števec
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                _global_item_counter = max((int(x.get('Zap', 0)) for x in data), default=0)
            log_and_print(f"Nadaljujem z Zap: {_global_item_counter}", to_file=True)
        except: pass

    query_date = datetime.now().strftime("%d/%m/%Y")
    all_data_buffer = []

    try:
        for cat_slug, subcats in CATEGORIES.items():
            cat_name = cat_slug.replace('-', ' ').capitalize()
            log_and_print(f"\n--- Kategorija: {cat_name} ---", to_file=True)

            for sub_slug in subcats:
                links = get_product_links_from_subcategory(cat_slug, sub_slug)
                links = sorted(list(set(links))) # Unikatni

                for i, link in enumerate(links):
                    # Tu bi lahko preverili, če že imamo URL v bazi, 
                    # ampak ker nimamo baze v pomnilniku, raje zajemamo vse in save_data združi.
                    
                    details = get_product_details(link, cat_name, sub_slug, query_date)
                    if details:
                        all_data_buffer.append(details)
                        
                        if len(all_data_buffer) >= 5:
                            save_data(all_data_buffer, json_path, excel_path)
                            all_data_buffer = [] # sprazni
                    
                    time.sleep(random.uniform(2.0, 5.0))
                
                # Shrani po koncu podkategorije
                if all_data_buffer:
                    save_data(all_data_buffer, json_path, excel_path)
                    all_data_buffer = []

    except KeyboardInterrupt:
        log_and_print("Prekinjeno.", to_file=True)
    except Exception as e:
        log_and_print(f"NAPAKA: {e}", to_file=True)
        import traceback
        traceback.print_exc(file=_log_file)
    finally:
        if all_data_buffer:
            save_data(all_data_buffer, json_path, excel_path)
        log_and_print("--- Končano ---", to_file=True)
        if _log_file: _log_file.close()

if __name__ == "__main__":
    main()