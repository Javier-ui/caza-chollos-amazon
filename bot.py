#!/usr/bin/env python3
import json
import os
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data.json"
POLL_SECONDS = 30
SCAN_SECONDS = 600
ONCE = "--once" in sys.argv
MARKETS = {
    "ES": "amazon.es", "DE": "amazon.de", "FR": "amazon.fr",
    "IT": "amazon.it", "NL": "amazon.nl", "BE": "amazon.com.be",
    "PL": "amazon.pl", "SE": "amazon.se"
}

running = True

def load_env():
    env = {}
    p = Path("/home/ubuntu/.env")
    if p.exists():
        for raw in p.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k})
    return env

ENV = load_env()
TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise SystemExit("Falta TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"


def read_state():
    if not DATA.exists():
        return {"subscribers": [], "offset": 0, "watchlist": [], "last_scan": None}
    try:
        return json.loads(DATA.read_text())
    except Exception:
        return {"subscribers": [], "offset": 0, "watchlist": [], "last_scan": None}

state = read_state()
lock = threading.Lock()


def save_state():
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    tmp.replace(DATA)


def api(method, payload=None, timeout=40):
    data = urllib.parse.urlencode(payload or {}).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def send(chat_id, text):
    try:
        api("sendMessage", {"chat_id": str(chat_id), "text": text, "disable_web_page_preview": "true"})
    except Exception as e:
        print(f"send error: {e}", flush=True)


def help_text():
    return ("Comandos disponibles:\n"
            "/start — activar alertas en este chat\n"
            "/estado — estado del bot y último barrido\n"
            "/mercados — marketplaces UE vigilados\n"
            "/silenciar — dejar de recibir alertas\n"
            "/ayuda — mostrar esta ayuda\n\n"
            "El motor de precios está en modo prudente: solo publicará ofertas cuando la fuente sea permitida y el precio pueda verificarse.")


def handle(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg or not msg.get("chat"):
        return
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    with lock:
        if command == "/start":
            if chat_id not in state["subscribers"]:
                state["subscribers"].append(chat_id)
                save_state()
            send(chat_id, "Bot activado para este chat.\n\n" + help_text())
        elif command in ("/ayuda", "/help"):
            send(chat_id, help_text())
        elif command == "/estado":
            last = state.get("last_scan") or "todavía no iniciado"
            send(chat_id, f"Estado: activo\nBarrido configurado: cada 10 minutos\nÚltimo ciclo: {last}\nFuentes automáticas: pendientes de activar con acceso permitido\nChats suscritos: {len(state['subscribers'])}")
        elif command == "/mercados":
            send(chat_id, "Marketplaces UE configurados:\n" + "\n".join(f"{k}: {v}" for k, v in MARKETS.items()))
        elif command == "/silenciar":
            if chat_id in state["subscribers"]:
                state["subscribers"].remove(chat_id)
                save_state()
            send(chat_id, "Alertas desactivadas en este chat. Usa /start para reactivarlas.")
        elif text:
            send(chat_id, "No reconozco ese comando. Usa /ayuda.")


def poll_loop():
    while running:
        try:
            with lock:
                offset = int(state.get("offset", 0))
            result = api("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": json.dumps(["message"])}, timeout=35)
            for upd in result.get("result", []):
                with lock:
                    state["offset"] = upd["update_id"] + 1
                    save_state()
                handle(upd)
        except Exception as e:
            print(f"poll error: {e}", flush=True)
            time.sleep(5)


def scan_loop():
    while running:
        with lock:
            state["last_scan"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
            save_state()
        # Deliberadamente no se hacen peticiones masivas: las fuentes de precios
        # deben configurarse y validarse antes de activar alertas automáticas.
        for _ in range(SCAN_SECONDS):
            if not running:
                return
            time.sleep(1)


def scan_once():
    with lock:
        state["last_scan"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
        save_state()
    # No se hacen peticiones masivas hasta validar las fuentes permitidas.


def poll_once():
    try:
        with lock:
            offset = int(state.get("offset", 0))
        result = api("getUpdates", {"offset": offset, "timeout": 1, "allowed_updates": json.dumps(["message"])}, timeout=8)
        for upd in result.get("result", []):
            with lock:
                state["offset"] = upd["update_id"] + 1
                save_state()
            handle(upd)
    except Exception as e:
        print(f"poll once error: {e}", flush=True)


def stop(*_):
    global running
    running = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
if ONCE:
    print("dealbot ejecución única", flush=True)
    poll_once()
    scan_once()
    raise SystemExit(0)
print("dealbot iniciado; polling activo; ciclo de barrido: 600 s", flush=True)
threading.Thread(target=scan_loop, daemon=True).start()
poll_loop()
print("dealbot detenido", flush=True)
