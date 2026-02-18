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
SHOP_NAME = "Merkur"
BASE_URL = "https://www.merkur.si"
DDV_RATE = 0.22

# --- Varnostne nastavitve ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

# Kategorije za Merkur
MERKUR_CATEGORIES = {
    "Osnovni gradbeni izdelki in les": [
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/gradbene-surovine/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/opazne-plosce-in-elementi/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/osb-in-lsb-plosce/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/opeka-prizme/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/malte-in-ometi/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/zagan-les-in-letve/",
        "https://www.merkur.si/gradnja/osnovni-gradbeni-izdelki-in-les/lepljenci/"
    ],
    "Termoizolacije": [
        "https://www.merkur.si/gradnja/termoizolacije/stiropor/",
        "https://www.merkur.si/gradnja/termoizolacije/estrudirani-polistiren-xps/",
        "https://www.merkur.si/gradnja/termoizolacije/steklena-volna/",
        "https://www.merkur.si/gradnja/termoizolacije/kamena-volna/",
        "https://www.merkur.si/gradnja/termoizolacije/folije/",
        "https://www.merkur.si/gradnja/termoizolacije/ostalo/"
    ],
    "Hidroizolacije": [
        "https://www.merkur.si/gradnja/hidroizolacije/bitumenski-trakovi-in-premazi/bitumenski-premazi/",
        "https://www.merkur.si/gradnja/hidroizolacije/bitumenski-trakovi-in-premazi/bitumenski-trakovi/",
        "https://www.merkur.si/gradnja/hidroizolacije/cementna-hidroizolacija/mrezica/"
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


def create_output_and_log_paths(shop_name):
    """Ustvari poti za output (excel+json) in log.

    GitHub/CI:
      - če je nastavljen env OUTPUT_DIR, se vse piše pod to mapo (npr. artifacts/)
      - drugače se piše ob skripti (kot prej)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_root = os.environ.get("OUTPUT_DIR", script_dir)

    # Ceniki_Scraping/<SHOP>/<YYYY-MM-DD>/
    main_dir = os.path.join(output_root, "Ceniki_Scraping")
    shop_dir = os.path.join(main_dir, shop_name)
    today_date_folder = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(shop_dir, today_date_folder)

    os.makedirs(daily_dir, exist_ok=True)

    filename_date = datetime.now().strftime("%d_%m_%Y")
    excel_filename = f"{shop_name}_Podatki_{filename_date}.xlsx"
    json_filename = f"{shop_name}_Podatki_{filename_date}.json"
    full_excel_path = os.path.join(daily_dir, excel_filename)
    full_json_path = os.path.join(daily_dir, json_filename)

    log_filename = f"{shop_name}_Scraping_Log_{datetime.now().strftime('%H-%M-%S')}.txt"
    log_filepath = os.path.join(daily_dir, log_filename)

    print(f"Izhodna pot za Excel: {full_excel_path}")
    print(f"Izhodna pot za JSON: {full_json_path}")
    print(f"Izhodna pot za log: {log_filepath}")

    return full_excel_path, full_json_path, log_filepath



def save_to_json(data, filepath):
    """Shrani podatke v JSON (UTF-8, pretty)."""
    if not data:
        log_and_print("Ni novih podatkov za shranjevanje v JSON.", to_file=True)
        return
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log_and_print(f"Podatki uspešno shranjeni v JSON: {filepath}", to_file=True)
    except Exception as e:
        log_and_print(f"Napaka pri shranjevanju v JSON: {e}", to_file=True)

def save_to_excel(data, filepath):
    if not data:
        log_and_print("Ni novih podatkov za shranjevanje v Excel.", to_file=True)
        return

    df_new = pd.DataFrame(data)

    try:
        if os.path.exists(filepath):
            existing_df = pd.read_excel(filepath)
            combined_df = pd.concat([existing_df, df_new], ignore_index=True)
        else:
            combined_df = df_new

        combined_df.drop_duplicates(subset=['URL'], keep='last', inplace=True)

        desired_columns = ["Skupina", "Zap", "Oznaka / naziv", "EAN", "Opis", "EM", "Valuta", "DDV", "Proizvajalec",
                           "Veljavnost od", "Dobava", "Cena / EM (z DDV)", "Akcijska cena / EM (z DDV)",
                           "Cena / EM (brez DDV)", "Akcijska cena / EM (brez DDV)", "URL", "SLIKA URL"]
        for col in desired_columns:
            if col not in combined_df.columns:
                combined_df[col] = ''

        df_final = combined_df[desired_columns].sort_values(by="Zap").reset_index(drop=True)
        df_final['Zap'] = df_final.index + 1

        df_final.to_excel(filepath, index=False)
        log_and_print(f"Podatki uspešno shranjeni/posodobljeni v: {filepath}", to_file=True)
    except Exception as e:
        error_msg = f"Napaka pri shranjevanju v Excel: {e}"
        log_and_print(error_msg, to_file=True)
        # TUKAJ SMO ZAMENJALI MESSAGEBOX S PRINTOM
        print(f"CRITICAL ERROR: {error_msg}")


def get_page_content(url):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        log_and_print(f"Napaka pri dostopu do URL-ja {url}: {e}", to_file=True)
        return None


def convert_price_to_without_vat(price_str, vat_rate):
    if not price_str or not isinstance(price_str, str): return ""
    try:
        cleaned_price = price_str.replace('.', '').replace(',', '.')
        price_with_vat = float(cleaned_price)
        price_without_vat = price_with_vat / (1 + vat_rate)
        return f"{price_without_vat:.2f}".replace('.', ',')
    except (ValueError, TypeError):
        return ""


def clean_price_string(price_str):
    if not price_str: return ""
    return re.sub(r'[^\d,]', '', price_str)


# --- Funkcije, specifične za Merkur ---

def get_product_details(product_url, group_name, query_date, item_html):
    """Pridobi podrobnosti o izdelku."""
    global _global_item_counter

    opis = item_html.h3.text.strip() if item_html.h3 else ""
    cena = ""
    cenastri_tag = item_html.span
    if cenastri_tag:
        cenaint = re.findall(r'[\d,]+', cenastri_tag.text.replace(".", ""))
        if cenaint:
            cena = cenaint[0] if len(cenaint) == 1 else cenaint[1]

    if not opis and not cena:
        log_and_print(f"      Preskakujem izdelek brez opisa in cene: {product_url}", to_file=True)
        return None

    log_and_print(f"    - Zajemanje podrobnosti za: {opis}", to_file=True)

    details_html = get_page_content(product_url)
    if not details_html: return None

    soup2 = BeautifulSoup(details_html, "html.parser")

    _global_item_counter += 1
    product_data = {
        "Skupina": group_name, "Zap": _global_item_counter, "URL": product_url,
        "Veljavnost od": query_date, "Valuta": "EUR", "DDV": "22", "EM": "KOS",
        "Opis": opis, "Cena / EM (z DDV)": cena
    }

    sifra_tag = soup2.find("div", class_="product-id")
    if sifra_tag:
        sifraint = re.findall(r'\d+', sifra_tag.text)
        product_data['Oznaka / naziv'] = sifraint[0] if sifraint else ''

    slikca_tag = item_html.find("img")
    product_data['SLIKA URL'] = slikca_tag.get("src") if slikca_tag else ''
    product_data['Cena / EM (brez DDV)'] = convert_price_to_without_vat(cena, DDV_RATE)

    return product_data


# --- Glavna funkcija ---

def main():
    global _log_file, _global_item_counter
    output_filepath, json_filepath, log_filepath = create_output_and_log_paths(SHOP_NAME)
    try:
        _log_file = open(log_filepath, 'w', encoding='utf-8')
    except Exception as e:
        print(f"CRITICAL ERROR: Ni mogoče ustvariti log datoteke: {e}")
        return

    log_and_print(f"--- Zagon zajemanja podatkov iz {SHOP_NAME} ---", to_file=True)
    all_products_data = []
    
    # Preverimo, če že obstaja datoteka in naložimo obstoječe
    if os.path.exists(output_filepath):
        try:
            existing_df = pd.read_excel(output_filepath)
            all_products_data = existing_df.to_dict(orient='records')
            if not existing_df.empty and 'Zap' in existing_df.columns:
                 # Varno branje max vrednosti
                numeric_zaps = pd.to_numeric(existing_df['Zap'], errors='coerce').dropna()
                if not numeric_zaps.empty:
                     _global_item_counter = int(numeric_zaps.max())
            log_and_print(f"Naloženi obstoječi podatki. Števec 'Zap' nastavljen na {_global_item_counter}.",
                          to_file=True)
        except Exception as e:
            log_and_print(f"Napaka pri nalaganju obstoječih podatkov: {e}. Začenjam na novo.", to_file=True)

    query_date = datetime.now().strftime("%d/%m/%Y")

    try:
        for main_category_name, subcategory_urls in MERKUR_CATEGORIES.items():
            log_and_print(f"\n--- Obdelujem glavno kategorijo: {main_category_name} ---", to_file=True)
            for sub_cat_url in subcategory_urls:
                sub_cat_name = sub_cat_url.strip('/').split('/')[-1]
                group_name_for_excel = sub_cat_name.replace('-', ' ').capitalize()

                log_and_print(f"\n  -- Začenjam obdelavo podkategorije: {group_name_for_excel} --", to_file=True)

                stariprvi = "star"
                n = 1
                new_data_for_category = []
                # Pripravimo set obstoječih URL-jev za hitrejše iskanje
                existing_urls = {d.get('URL') for d in all_products_data if d.get('URL')}

                while True:
                    paginated_url = f"{sub_cat_url}?p={n}#section-products"
                    log_and_print(f"    Obdelujem stran {n}: {paginated_url}", to_file=True)

                    html_content = get_page_content(paginated_url)
                    if not html_content: break

                    soup1 = BeautifulSoup(html_content, 'lxml')
                    item_container = soup1.find("div", class_="list-items")
                    if not item_container: break

                    izdelek_list = item_container.find_all("div", class_="item")
                    if not izdelek_list: break

                    noviprvi = izdelek_list[0].h3.text.strip() if izdelek_list[0].h3 else None
                    if n > 1 and noviprvi == stariprvi:
                        log_and_print(f"      Vsebina strani {n} se ponavlja. Zaključujem.", to_file=True)
                        break
                    stariprvi = noviprvi

                    for i in izdelek_list:
                        link_tag = i.find("a")
                        if not (link_tag and link_tag.get("href")): continue

                        product_url = link_tag.get("href")
                        if product_url in existing_urls: continue

                        # Podatke posredujemo v funkcijo
                        details = get_product_details(product_url, group_name_for_excel, query_date, i)

                        if details:
                            new_data_for_category.append(details)
                            # Dodamo v set, da ne podvajamo znotraj istega teka
                            existing_urls.add(product_url)
                            
                            if len(new_data_for_category) % 5 == 0:
                                save_to_excel(all_products_data + new_data_for_category, output_filepath)

                        is_ci = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
                        if is_ci:
                            time.sleep(random.uniform(0.7, 2.5))   # hitreje na GitHubu
                        else:
                            time.sleep(random.uniform(2.0, 20.0))  # počasneje lokalno

                    if not soup1.select_one('a.next'): break
                    n += 1

                if new_data_for_category:
                    all_products_data.extend(new_data_for_category)
                    save_to_json(all_products_data, json_filepath)
        save_to_excel(all_products_data, output_filepath)

    except KeyboardInterrupt:
        log_and_print("\nSkripta prekinjena. Shranjujem zajete podatke...", to_file=True)
    except Exception as e:
        log_and_print(f"\nNEPRIČAKOVANA NAPAKA: {e}", to_file=True)
        import traceback
        traceback.print_exc(file=_log_file)
        # ZAMENJAVA MESSAGEBOX S PRINTOM
        print(f"Nepričakovana napaka: {e}. Podrobnosti so v logu.")
    finally:
        save_to_json(all_products_data, json_filepath)
        save_to_excel(all_products_data, output_filepath)
        log_and_print("\n--- Zajemanje zaključeno ---", to_file=True)
        print(f"Zaključeno. Podatki so v: {output_filepath} in {json_filepath}")
        if _log_file:
            _log_file.close()

# --- ZAGON BREZ GUI ---
if __name__ == "__main__":
    main()
