#!/usr/bin/env python3
import html
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data.json"
TARGET_CHAT = os.environ.get("TARGET_CHAT_ID", "-1003980825772")
MIN_DISCOUNT = float(os.environ.get("MIN_DISCOUNT", "25"))
CATEGORY_DELAY = float(os.environ.get("CATEGORY_DELAY_SECONDS", "10"))
MAX_RETRIES_503 = int(os.environ.get("MAX_RETRIES_503", "3"))

MARKETS = [
    ("ES", "amazon.es", "es-ES,es;q=0.9"),
    ("DE", "amazon.de", "de-DE,de;q=0.9"),
    ("FR", "amazon.fr", "fr-FR,fr;q=0.9"),
    ("IT", "amazon.it", "it-IT,it;q=0.9"),
    ("NL", "amazon.nl", "nl-NL,nl;q=0.9"),
    ("BE", "amazon.com.be", "fr-BE,fr;q=0.9"),
    ("PL", "amazon.pl", "pl-PL,pl;q=0.9"),
    ("SE", "amazon.se", "sv-SE,sv;q=0.9"),
]

# Consultas de alto valor de reventa. Las cinco últimas son específicamente Warehouse.
CATEGORIES = [
    ("tarjetas gráficas", "graphics card"),
    ("portátiles gaming", "gaming laptop"),
    ("portátiles profesionales", "business laptop"),
    ("smartphones premium", "smartphone unlocked"),
    ("iPhone", "iphone"),
    ("tablets premium", "tablet pro"),
    ("consolas", "game console"),
    ("PS5", "playstation 5"),
    ("Xbox", "xbox series x"),
    ("Nintendo Switch", "nintendo switch oled"),
    ("cámaras mirrorless", "mirrorless camera"),
    ("objetivos", "camera lens"),
    ("drones", "camera drone"),
    ("smartwatches", "premium smartwatch"),
    ("SSD NVMe", "nvme ssd 2tb"),
    ("NAS", "nas storage"),
    ("routers WiFi premium", "wifi 6 router"),
    ("monitores gaming", "gaming monitor 144hz"),
    ("memoria RAM", "ddr5 ram kit"),
    ("procesadores", "desktop processor"),
    ("placas base", "motherboard"),
    ("fuentes de alimentación", "modular power supply"),
    ("herramientas profesionales", "professional cordless tools"),
    ("taladros", "cordless drill"),
    ("aspiradores premium", "robot vacuum"),
    ("Warehouse electrónica", "electronics"),
    ("Warehouse informática", "laptop"),
    ("Warehouse gaming", "gaming"),
    ("Warehouse cámaras", "camera"),
    ("Warehouse herramientas", "power tools"),
]


def load_state():
    if not DATA.exists():
        return {"subscribers": [], "offset": 0, "watchlist": [], "last_scan": None, "market_index": 0, "sent": {}}
    try:
        state = json.loads(DATA.read_text())
        state.setdefault("market_index", 0)
        state.setdefault("sent", {})
        return state
    except Exception:
        return {"subscribers": [], "offset": 0, "watchlist": [], "last_scan": None, "market_index": 0, "sent": {}}


def save_state(state):
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(DATA)


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def to_number(raw):
    raw = raw.replace("\xa0", " ").strip()
    raw = re.sub(r"[^0-9,.]", "", raw)
    if not raw:
        return None
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[-1]
        raw = raw.replace(",", ".") if len(tail) in (1, 2) else raw.replace(",", "")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def fetch(url, language):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CholloPulse/1.0; +https://github.com/Javier-ui/caza-chollos-amazon)",
        "Accept-Language": language,
        "Accept": "text/html,application/xhtml+xml",
    }
    for attempt in range(MAX_RETRIES_503 + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code != 503 or attempt >= MAX_RETRIES_503:
                print(f"HTTP {exc.code}: {url}", flush=True)
                return ""
            delay = min(90, 20 * (2 ** attempt)) + random.uniform(0, 5)
            print(f"503; reintento {attempt + 1}/{MAX_RETRIES_503} en {delay:.1f}s", flush=True)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"error de red: {exc}", flush=True)
            return ""
    return ""


def parse_items(page, domain, query, warehouse=False):
    items = []
    for match in re.finditer(r'data-asin="([A-Z0-9]{8,})"', page):
        asin = match.group(1)
        block = page[match.start(): match.start() + 50000]
        title_match = re.search(r'class="a-size-medium[^>]*>(.*?)</span>', block, re.S)
        if not title_match:
            title_match = re.search(r'class="a-size-base[^>]*>(.*?)</span>', block, re.S)
        title = clean(title_match.group(1)) if title_match else query
        price_matches = re.findall(r'class="a-price-whole"[^>]*>(.*?)</span>', block, re.S)
        frac_matches = re.findall(r'class="a-price-fraction"[^>]*>(.*?)</span>', block, re.S)
        if not price_matches:
            continue
        current = to_number(clean(price_matches[0]) + (clean(frac_matches[0]) if frac_matches else ""))
        old_matches = re.findall(r'class="a-text-price"[^>]*>.*?class="a-offscreen"[^>]*>(.*?)</span>', block, re.S)
        old = to_number(clean(old_matches[0])) if old_matches else None
        discount = ((old - current) / old * 100) if old and current and old > current else None
        if not current or not discount or discount < MIN_DISCOUNT:
            continue
        url = f"https://{domain}/dp/{asin}"
        items.append({"asin": asin, "title": title[:180], "current": current, "old": old, "discount": discount, "url": url, "warehouse": warehouse})
    return items[:3]


def scan():
    state = load_state()
    market_index = int(state.get("market_index", 0)) % len(MARKETS)
    code, domain, language = MARKETS[market_index]
    state["market_index"] = (market_index + 1) % len(MARKETS)
    alerts = []
    for index, (label, query) in enumerate(CATEGORIES):
        warehouse = label.startswith("Warehouse")
        params = {"k": query, "ref": "sr_nr_p_n_condition-type_0"}
        if warehouse:
            params["i"] = "warehouse-deals"
        url = f"https://{domain}/s?{urllib.parse.urlencode(params)}"
        print(f"[{code}] {index + 1}/{len(CATEGORIES)} {label}", flush=True)
        page = fetch(url, language)
        alerts.extend(parse_items(page, domain, query, warehouse))
        if index < len(CATEGORIES) - 1:
            time.sleep(CATEGORY_DELAY + random.uniform(0, 4))
    unique = []
    for item in alerts:
        key = f"{domain}:{item['asin']}"
        previous = state["sent"].get(key, 0)
        if time.time() - previous >= 86400:
            state["sent"][key] = time.time()
            unique.append(item)
    state["last_scan"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
    # Conserva solo una ventana acotada de deduplicación.
    state["sent"] = {k: v for k, v in state["sent"].items() if time.time() - v < 172800}
    save_state(state)
    return code, unique


def format_alert(code, item):
    tag = "Warehouse" if item["warehouse"] else "Nuevo"
    return (f"{tag} posible chollo — Amazon {code}\n"
            f"{item['title']}\n"
            f"Precio mostrado: {item['current']:.2f}\n"
            f"Referencia mostrada: {item['old']:.2f}\n"
            f"Descuento mostrado: {item['discount']:.0f}%\n"
            f"ASIN: {item['asin']}\n"
            f"{item['url']}\n\n"
            "Verifica vendedor, estado, garantía y gastos antes de comprar.")
