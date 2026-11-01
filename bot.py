"""KakoBuy -> Telegram. Python 3.12+, solo libreria standard."""
import argparse
import hashlib
import html
import io
import json
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def http(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, headers={"User-Agent": "KakoBuyTelegramBot/1.0",
                                              "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        # Non stampare l'URL: per Telegram contiene il token.
        raise RuntimeError(f"Richiesta HTTP rifiutata: {exc.code}.") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Richiesta di rete fallita o scaduta.") from None


def valid_url(value):
    try:
        parts = urlsplit(value)
        return parts.scheme in ("http", "https") and bool(parts.hostname) and not parts.username
    except ValueError:
        return False


def product_key(link):
    """Identifica il prodotto sorgente, ignorando affcode e cambi di dominio agente."""
    parts = urlsplit(link)
    query = parse_qs(parts.query)
    source = query.get("url", [link])[0]
    inner = urlsplit(source)
    values = parse_qs(inner.query)
    item_id = values.get("itemID", values.get("id", []))
    if item_id:
        domain = (inner.hostname or "").lower().removeprefix("www.")
        canonical = domain + ":" + item_id[0]
    else:
        clean = {k: v for k, v in values.items()
                 if k.lower() not in ("affcode", "ref", "spm") and not k.lower().startswith("utm_")}
        canonical = urlunsplit((inner.scheme.lower(), inner.netloc.lower(), inner.path,
                               urlencode(sorted(clean.items()), doseq=True), ""))
    return hashlib.sha256(canonical.encode()).hexdigest()


def column(index):
    value = ""
    while index:
        index, digit = divmod(index - 1, 26)
        value = chr(65 + digit) + value
    return value


def column_number(ref):
    value = 0
    for char in re.match(r"[A-Z]+", ref)[0]:
        value = value * 26 + ord(char) - 64
    return value


def rels(archive, path):
    name = posixpath.join(posixpath.dirname(path), "_rels", posixpath.basename(path) + ".rels")
    if name not in archive.namelist():
        return {}
    return {r.get("Id"): r.get("Target") for r in ET.fromstring(archive.read(name))}


def parse_workbook(data, selected, audit=None):
    """Legge blocchi PRODUCT / KAKOBUY LINK / PRICE / IMAGE, anche affiancati."""
    products, seen, matched = [], {}, set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in item.findall(".//s:t", NS))
                       for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        mapping = rels(archive, "xl/workbook.xml")
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            name = sheet.get("name").strip()
            if selected and name not in {s.strip() for s in selected}:
                continue
            if sheet.get("state", "visible") != "visible":
                continue
            matched.add(name)
            stats = {"sheet": name, "candidates": 0, "valid": 0, "new_unique": 0,
                     "missing_ninjabuy": 0, "invalid_photo": 0, "invalid_price": 0,
                     "invalid_kakobuy": 0}
            if audit is not None:
                audit.append(stats)
            target = mapping[sheet.get(RID)]
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
            root = ET.fromstring(archive.read(path))
            cells = {}
            for cell in root.findall(".//s:sheetData/s:row/s:c", NS):
                val, formula = cell.find("s:v", NS), cell.find("s:f", NS)
                value = val.text or "" if val is not None else ""
                if cell.get("t") == "s":
                    value = strings[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                cells[cell.get("r")] = (value.strip(), formula.text or "" if formula is not None else "")
            links = rels(archive, path)
            hyperlinks = {h.get("ref"): links.get(h.get(RID), "")
                          for h in root.findall("s:hyperlinks/s:hyperlink", NS)}

            def get(c, r):
                return cells.get(f"{column(c)}{r}", ("", ""))

            def cell_link(c, r):
                link = hyperlinks.get(f"{column(c)}{r}") or get(c, r)[0]
                if not valid_url(link):
                    match = re.search(r'HYPERLINK\(\s*"([^"]+)"', get(c, r)[1], re.I)
                    link = match[1] if match else ""
                return link

            blocks = []
            for ref, (text, _) in cells.items():
                if text.upper() != "PRODUCT":
                    continue
                c, r = column_number(ref), int(re.search(r"\d+", ref)[0])
                # Alcuni gruppi hanno una colonna vuota aggiuntiva: H/J/K/M/N.
                fields = []
                for field_col in range(c + 1, c + 8):
                    label = get(field_col, r)[0].upper()
                    if label == "PRODUCT":
                        break
                    fields.append((field_col, label))
                kak = next((fc for fc, label in fields if "KAKOBUY" in label), None)
                image_col = next((fc for fc, label in fields if label == "IMAGE"), None)
                prices = [fc for fc, label in fields if label == "PRICE"]
                if kak and image_col and prices:
                    blocks.append((c, r, kak, image_col, prices))
            last_row = max((int(re.search(r"\d+", ref)[0]) for ref in cells), default=0)
            for row in range(1, last_row + 1):
                for col, header, kak_col, image_col, price_cols in blocks:
                    if row <= header:
                        continue
                    title = get(col, row)[0]
                    if not title or title.upper() == "PRODUCT":
                        continue
                    # Evita intestazioni di categoria e righe descrittive.
                    link = cell_link(kak_col, row)
                    if not link and not get(image_col, row)[1]:
                        continue
                    stats["candidates"] += 1
                    if not valid_url(link):
                        stats["invalid_kakobuy"] += 1
                        continue
                    if (urlsplit(link).hostname or "").lower() not in (
                        "kakobuy.com", "www.kakobuy.com", "item.kakobuy.com", "item2.kakobuy.com"
                    ):
                        stats["invalid_kakobuy"] += 1
                        continue
                    ninja = next((cell_link(nc, row) for nc in range(col + 1, kak_col)
                                  if (urlsplit(cell_link(nc, row)).hostname or "").lower()
                                  in ("ninjabuy.com", "www.ninjabuy.com")), "")
                    if not ninja:
                        stats["missing_ninjabuy"] += 1
                    image = re.search(r'IMAGE\(\s*"([^"]+)"', get(image_col, row)[1], re.I)
                    photo = image[1] if image else get(image_col, row)[0]
                    if not valid_url(photo):
                        stats["invalid_photo"] += 1
                        continue
                    # Celle del foglio attuale: USD sulla riga prodotto, EUR sotto.
                    price_col = price_cols[-1]
                    usd, usd_formula = get(price_col, row)
                    eur, eur_formula = get(price_col, row + 1)
                    rate_pattern = r"/(?:'[^']+'!)?\$D\$\d+"
                    if re.search(rate_pattern, usd_formula) and re.search(rate_pattern, eur_formula):
                        try:
                            price = f"€{float(eur):.2f} · ${float(usd):.2f}"
                        except ValueError:
                            stats["invalid_price"] += 1
                            continue
                    else:
                        # Layout precedenti: prezzo testuale con simbolo monetario.
                        price = next((get(pc, row)[0] for pc in price_cols
                                      if any(s in get(pc, row)[0] for s in ("$", "€", "¥"))), "")
                        if not any(symbol in price for symbol in ("$", "€", "¥")):
                            stats["invalid_price"] += 1
                            continue
                    stats["valid"] += 1
                    key = product_key(link)
                    source = f"{name}!{column(col)}{row}"
                    if key in seen:
                        if source not in seen[key]["sources"]:
                            seen[key]["sources"].append(source)
                        if not seen[key]["ninjabuy_link"] and ninja:
                            seen[key]["ninjabuy_link"] = ninja
                        continue
                    stats["new_unique"] += 1
                    product = dict(key=key, title=title, price=price, photo=photo,
                                         link=link, ninjabuy_link=ninja,
                                         source=source, sources=[source])
                    seen[key] = product
                    products.append(product)
    missing = {s.strip() for s in selected} - matched
    if missing:
        raise RuntimeError("Schede visibili non trovate: " + ", ".join(sorted(missing)))
    if not products:
        raise RuntimeError("Nessun prodotto valido: controlla layout, immagini e link KakoBuy.")
    return products


def telegram(token, method, payload):
    result = json.loads(http(f"https://api.telegram.org/bot{token}/{method}", payload))
    if not result.get("ok"):
        raise RuntimeError("Telegram ha rifiutato la richiesta.")
    return result["result"]


def caption(product, config):
    # Limite calcolato anche in unità UTF-16 (emoji incluse).
    def anchor(url, label):
        if not valid_url(url):
            raise RuntimeError("URL non valido nella configurazione del messaggio.")
        return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
    spreadsheet = f"https://docs.google.com/spreadsheets/d/{config.get('spreadsheet_id', '')}/edit"
    lines = [anchor(spreadsheet, "📑 BEST SPREADSHEET 📑"),
             "🔎 Article: " + html.escape(product['title'][:220]),
             "💵 " + html.escape(product['price']),
             anchor(product['link'], "🔗 KakoBuy Link"),
             anchor(product['ninjabuy_link'], "🔗 NinjaBuy Link"),
             "", html.escape(config['footer'][:160])]
    social = []
    for key, label in (("haul_url", "▶️ Haul"), ("shorts_url", "🎵 Shorts")):
        if config.get(key):
            social.append(anchor(config[key], label))
    if social:
        lines.extend(["", "My social: " + " · ".join(social)])
    if config.get("register_url"):
        lines.extend(["", anchor(config['register_url'], config.get('register_label', '🎉 Register Here 🎉'))])
    text = "\n".join(lines)
    visible = html.unescape(re.sub(r'<[^>]+>', '', text))
    if len(visible.encode("utf-16-le")) // 2 > 1024:
        raise RuntimeError("Didascalia troppo lunga.")
    return text


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Salvataggio Git fallito: nessun nuovo invio verrà tentato.")
    return result.stdout


def save_state(state, persist):
    path = ROOT / "state.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    if persist:
        git("add", "--", "state.json")
        git("commit", "-m", "Update Telegram delivery state [skip ci]")
        git("push", "origin", "HEAD:main")


def publish(products, config, state, token, chat, persist):
    pending = sum(x["status"] == "pending" for x in state["items"].values())
    if pending:
        raise RuntimeError(f"{pending} invii incerti in state.json: risolverli prima di proseguire.")
    count = 0
    for product in products:
        key = product["key"]
        if key in state["items"]:
            continue
        if not product.get("ninjabuy_link"):
            print("Prodotto saltato: manca il link NinjaBuy.")
            continue
        text = caption(product, config)
        state["items"][key] = {"status": "pending", "source": product["source"],
                               "at": datetime.now(timezone.utc).isoformat()}
        # Prenota su GitHub PRIMA dell'invio. Nessun retry automatico dopo timeout.
        save_state(state, persist)
        message = telegram(token, "sendPhoto", {
            "chat_id": chat, "photo": product["photo"], "caption": text, "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": config["button_text"],
                                                     "url": product["link"]},
                                                    {"text": "🛒 NinjaBuy", "url": product["ninjabuy_link"]}]]}})
        state["items"][key].update(status="sent", message_id=message["message_id"])
        save_state(state, persist)
        count += 1
        print(f"Pubblicato prodotto {count}; stato salvato.")
        if count >= config["max_posts"]:
            break
    if not count:
        print("Nessun nuovo prodotto da pubblicare.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preview", "check", "publish"], default="preview")
    parser.add_argument("--xlsx", help="Esportazione locale, utile per test offline")
    parser.add_argument("--persist-git", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if not 1 <= config["max_posts"] <= 5:
        raise RuntimeError("max_posts deve essere tra 1 e 5.")
    if args.mode == "check":
        token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
        me = telegram(token, "getMe", {})
        target = telegram(token, "getChat", {"chat_id": chat})
        member = telegram(token, "getChatMember", {"chat_id": chat, "user_id": me["id"]})
        if target["type"] != "channel" or member["status"] != "administrator" or not member.get("can_post_messages"):
            raise RuntimeError("Il bot deve essere amministratore del canale con diritto di pubblicare.")
        print("Token, canale e permessi verificati. Nessun messaggio inviato.")
        return
    data = Path(args.xlsx).read_bytes() if args.xlsx else http(
        f"https://docs.google.com/spreadsheets/d/{config['spreadsheet_id']}/export?format=xlsx")
    audit = []
    products = parse_workbook(data, config["sheet_names"], audit)
    for stats in audit:
        print(json.dumps(stats, ensure_ascii=True))
    state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("items"), dict):
        raise RuntimeError("Formato state.json non valido.")
    print(f"Prodotti validi unici: {len(products)}; già registrati: {len(state['items'])}.")
    if args.mode == "preview":
        for product in [p for p in products if p["key"] not in state["items"] and p.get("ninjabuy_link")][:config["max_posts"]]:
            print(json.dumps(product, ensure_ascii=True, indent=2))
            print(json.dumps({"caption": caption(product, config)}, ensure_ascii=True))
        print("Anteprima: nessun messaggio inviato, stato invariato.")
        return
    if not args.persist_git and os.environ.get("GITHUB_ACTIONS") == "true":
        raise RuntimeError("In Actions è obbligatorio --persist-git.")
    publish(products, config, state, os.environ["TELEGRAM_BOT_TOKEN"],
            os.environ["TELEGRAM_CHAT_ID"], args.persist_git)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError, OSError) as exc:
        # Errori controllati senza traceback contenente URL con credenziali.
        print(f"ERRORE: {exc}", file=sys.stderr)
        sys.exit(1)
