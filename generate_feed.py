# generate_feed.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from restaurants import restaurants
import html
import re

# -----------------------------------
# CONFIG
# -----------------------------------
WEEKDAYS = {
    0: "Maanantai",
    1: "Tiistai",
    2: "Keskiviikko",
    3: "Torstai",
    4: "Perjantai"
}

today_index = datetime.today().weekday()
today_name = WEEKDAYS.get(today_index, "")


# -----------------------------------
# HELPERS
# -----------------------------------

def fetch_html(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def clean_menu_items(items):
    """Format items into Markdown bullets with proper line breaks."""
    cleaned = [line.strip() for line in items if line and line.strip()]
    if not cleaned:
        return "Menu not found"
    return "".join(f"• {line}  \n" for line in cleaned)


def contains_stop(text, stop_after):
    if not text or not stop_after:
        return False
    lower_text = text.lower()
    return any(stop.lower() in lower_text for stop in stop_after)


def first_stop_index(text, stop_after):
    lower_text = text.lower()
    idxs = [lower_text.find(stop.lower()) for stop in (stop_after or []) if lower_text.find(stop.lower()) != -1]
    return min(idxs) if idxs else -1


# -----------------------------------
# PARSERS (unchanged)
# -----------------------------------

def parse_table_menu(soup, today_name):
    table = soup.find("table", class_="lunch-list-table")
    if not table:
        return "Menu not found"
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if not cols:
            continue
        day_text = cols[0].get_text(" ", strip=True)
        if today_name.lower() in day_text.lower():
            menu_text = cols[1].get_text(separator="\n", strip=True)
            items = [it.strip() for part in re.split(r"\n|,", menu_text) for it in [part] if it.strip()]
            return clean_menu_items(items)
    return "Menu not found"


def parse_list_menu(soup, today_name):
    for li in soup.find_all("li", class_="menu-group-item"):
        heading = li.find(class_="food-item-heading")
        heading_text = heading.get_text(" ", strip=True) if heading else li.get_text(" ", strip=True)
        if today_name.lower() in heading_text.lower():
            items = [p.get_text(" ", strip=True) for p in li.find_all("p") if p.get_text(strip=True)]
            return clean_menu_items(items)
    return "Menu not found"


def parse_div_snippet(soup, today_name, stop_after=None):
    """For Persilja: stops before 'ERIKOIS...' section."""
    for p in soup.find_all():
        if p.name and today_name in p.get_text(" ", strip=True):
            items = []
            sib = p.find_next_sibling()
            while sib:
                text = sib.get_text(" ", strip=True)
                if not text:
                    sib = sib.find_next_sibling()
                    continue
                if any(day in text for day in WEEKDAYS.values()):
                    break
                if stop_after and contains_stop(text, stop_after):
                    idx = first_stop_index(text, stop_after)
                    if idx > 0:
                        prefix = text[:idx].strip()
                        if prefix:
                            items.append(prefix)
                    break
                items.append(text)
                sib = sib.find_next_sibling()
            return clean_menu_items(items)
    return "Menu not found"


def parse_simple_p(soup, today_name, stop_after=None):
    """For Pisara: stops before 'Lisätietoja allergeeneista'."""
    sections = soup.find_all("p")
    capture = False
    items = []
    for p in sections:
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        if today_name in text:
            capture = True
            continue
        if capture:
            if any(day in text for day in WEEKDAYS.values()):
                break
            if stop_after and contains_stop(text, stop_after):
                idx = first_stop_index(text, stop_after)
                if idx > 0:
                    prefix = text[:idx].strip()
                    if prefix:
                        items.append(prefix)
                break
            items.append(text)
    return clean_menu_items(items)


# -----------------------------------
# MAKIATA SPECIAL (no date check)
# -----------------------------------

def parse_makiata_lauttasaari(soup):
    """Always pull Lauttasaari section (no week restriction)."""
    header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4", "h5"]
                       and "lauttasaari" in tag.get_text(" ", strip=True).lower())
    if header:
        # Try the table under Lauttasaari
        table = header.find_next("table", class_="lunch-list-table")
        if table:
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if not cols:
                    continue
                day_text = cols[0].get_text(" ", strip=True)
                if today_name.lower() in day_text.lower():
                    menu_text = cols[1].get_text(separator="\n", strip=True)
                    items = [it.strip() for part in re.split(r"\n|,", menu_text) for it in [part] if it.strip()]
                    return clean_menu_items(items)
        # fallback: paragraphs
        items = []
        sib = header.find_next_sibling()
        while sib:
            text = sib.get_text(" ", strip=True)
            if not text:
                sib = sib.find_next_sibling()
                continue
            if any(x.lower() in text.lower() for x in ["haaga", "espoo", "otaniemi"]):
                break
            if any(day in text for day in WEEKDAYS.values()):
                break
            items.append(text)
            sib = sib.find_next_sibling()
        return clean_menu_items(items) if items else "Menu not found"

    return "Menu not found"


# -----------------------------------
# DISPATCHER (special parsers for Persilja & Casa Mare)
# -----------------------------------

def parse_persilja_alternate(soup, today_name):
    """Alternate approach: search raw text, find today's block and trim at ERIKOIS variants."""
    content = soup.get_text("\n", strip=True)
    start = content.find(today_name)
    if start == -1:
        return "Menu not found"
    section = content[start:]
    # cut at ERIKOIS variants
    for stopword in ["ERIKOISANNOS", "ERIKOIS LOUNAS", "ERIKOISLOUNAS", "ERIKOIS"]:
        pos = section.upper().find(stopword.upper())
        if pos != -1:
            section = section[:pos]
    lines = [ln.strip() for ln in section.split("\n") if ln.strip() and not ln.strip().startswith(today_name)]
    if not lines:
        return "Menu not found"
    return clean_menu_items(lines)


def parse_casamare_fallback(soup, today_name):
    """Casa Mare fallback: search for elements mentioning today_name or weekday, gather next paras."""
    # search for paragraph or headings that mention the weekday or the date
    target = None
    # first try: find a <p> that contains the weekday string
    for p in soup.find_all(["p", "div", "h2", "h3", "h4"]):
        text = p.get_text(" ", strip=True)
        if today_name in text or "lounas" in text.lower() and "lauttasaari" in text.lower():
            target = p
            break
    if not target:
        # fallback: any p containing the word "Lounas"
        for p in soup.find_all("p"):
            if "lounas" in p.get_text(" ", strip=True).lower():
                target = p
                break
    if not target:
        return "Menu not found"

    items = []
    sib = target.find_next_sibling()
    while sib:
        text = sib.get_text(" ", strip=True)
        if not text:
            sib = sib.find_next_sibling()
            continue
        if any(day in text for day in WEEKDAYS.values()):
            break
        # also stop at common footer words
        if "hinnasto" in text.lower() or "osoite" in text.lower():
            break
        items.append(text)
        sib = sib.find_next_sibling()
    return clean_menu_items(items) if items else "Menu not found"


def fetch_today_menu(restaurant, today_name):
    html_text = fetch_html(restaurant["url"])
    soup = BeautifulSoup(html_text, "html.parser")
    type_ = restaurant.get("type", "")
    name = restaurant.get("name", "").lower()
    url = restaurant["url"].lower()

    # Persilja: try dedicated parser first, then alternate if needed
    if "persilja" in name or "persilja" in url:
        # first try div_snippet style (keeps structure), then raw-text fallback
        res = parse_div_snippet(soup, today_name, stop_after=["ERIKOIS", "ERIKOIS LOUNAS", "ERIKOISLOUNAS", "ERIKOIS ANNOS"])
        if res == "Menu not found":
            res = parse_persilja_alternate(soup, today_name)
        return res

    # Casa Mare: try table/div/p parsing, then fallback
    if "casa" in name or "casamare" in url or "casa-mare" in url:
        # try table/div approach from earlier version
        # Try table rows first
        table_try = None
        table = soup.find("table")
        if table:
            for row in table.find_all("tr"):
                if today_name in row.get_text(" ", strip=True):
                    tds = row.find_all("td")
                    if len(tds) > 1:
                        table_try = tds[1].get_text(" ", strip=True)
                        break
        if table_try:
            # split into items
            items = [it.strip() for part in re.split(r"\n|,", table_try) for it in [part] if it.strip()]
            return clean_menu_items(items)
        # fallback paragraph/div approach
        res = parse_casamare_fallback(soup, today_name)
        return res

    # Makiata special
    if "makiata" in url or "makiata" in name:
        return parse_makiata_lauttasaari(soup)

    # Default flows for the remaining restaurants
    if type_ == "table":
        return parse_table_menu(soup, today_name)
    if type_ == "list":
        return parse_list_menu(soup, today_name)
    if type_ == "div_snippet":
        return parse_div_snippet(soup, today_name)
    if type_ == "simple_p":
        return parse_simple_p(soup, today_name)

    return "Menu type unknown"


# -----------------------------------
# FEED GENERATION + SAVE
# -----------------------------------

def build_feed():
    feed = []
    for r in restaurants:
        try:
            menu = fetch_today_menu(r, today_name)
        except Exception as e:
            menu = f"Error fetching menu: {e}"
        feed.append({
            "name": r["name"],
            "hours": r.get("hours", ""),
            "prices": r.get("prices", {}),
            "menu": menu
        })
    return feed


def save_feed(feed):
    date_str = datetime.today().strftime("%d.%m.%Y")

    # README.md
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(f"# 🍽️ Lauttasaari Lunch Menus — {date_str}\n\n")
        f.write(f"### {today_name}\n\n")
        for item in feed:
            f.write(f"## {item['name']}\n")
            if item["hours"]:
                f.write(f"**Opening hours:** {item['hours']}\n\n")
            if item["prices"]:
                f.write("**Prices:**\n")
                for k, v in item["prices"].items():
                    f.write(f"- {k}: {v}\n")
                f.write("\n")
            f.write(f"**{today_name} menu:**\n\n")  # newline before bullets
            f.write(f"{item['menu']}\n\n")
            f.write("---\n\n")

    # feed.xml
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<lunchFeed>\n")
        f.write(f"  <date>{html.escape(date_str)}</date>\n")
        f.write(f"  <day>{html.escape(today_name)}</day>\n")
        for item in feed:
            f.write("  <restaurant>\n")
            f.write(f"    <name>{html.escape(item['name'])}</name>\n")
            if item["hours"]:
                f.write(f"    <hours>{html.escape(item['hours'])}</hours>\n")
            for k, v in item["prices"].items():
                f.write(f"    <price name='{html.escape(k)}'>{html.escape(v)}</price>\n")
            f.write(f"    <menu><![CDATA[{item['menu']}]]></menu>\n")
            f.write("  </restaurant>\n")
        f.write("</lunchFeed>\n")


def update_feed():
    feed = build_feed()
    save_feed(feed)
    for item in feed:
        print(f"--- {item['name']} ---")
        print(f"Opening hours: {item['hours']}")
        print("Prices:")
        for k, v in item["prices"].items():
            print(f"  {k}: {v}")
        print(f"{today_name} menu:\n{item['menu']}\n")


if __name__ == "__main__":
    update_feed()