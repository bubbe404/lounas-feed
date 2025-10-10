# generate_feed.py

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from restaurants import restaurants
import html

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
    """Format items into a bullet list with line breaks."""
    cleaned = [line.strip() for line in items if line.strip()]
    if not cleaned:
        return "Menu not found"
    return "\n".join(f"• {line}" for line in cleaned)


def contains_stop(text, stop_after):
    """Case-insensitive stop word check."""
    if not text:
        return False
    lower_text = text.lower()
    return any(stop.lower() in lower_text for stop in (stop_after or []))


# -----------------------------------
# PARSERS
# -----------------------------------

def parse_table_menu(soup, today_name):
    table = soup.find("table", class_="lunch-list-table")
    if not table:
        return "Menu not found"
    for row in table.find_all("tr"):
        if today_name in row.text:
            return clean_menu_items([row.find_all("td")[1].text])
    return "Menu not found"


def parse_list_menu(soup, today_name):
    for li in soup.find_all("li", class_="menu-group-item"):
        if today_name.lower() in li.text.lower():
            items = [p.text for p in li.find_all("p")]
            return clean_menu_items(items)
    return "Menu not found"


def parse_div_snippet(soup, today_name, stop_after=None):
    for p in soup.find_all("p"):
        if today_name in p.text:
            items = []
            next_sib = p.find_next_sibling("p")
            while next_sib and not any(day in next_sib.text for day in WEEKDAYS.values()):
                text = next_sib.text.strip()
                if not text:
                    next_sib = next_sib.find_next_sibling("p")
                    continue
                if contains_stop(text, stop_after):
                    break
                items.append(text)
                next_sib = next_sib.find_next_sibling("p")
            return clean_menu_items(items)
    return "Menu not found"


def parse_simple_p(soup, today_name, stop_after=None):
    sections = soup.find_all("p")
    capture = False
    items = []
    for p in sections:
        text = p.text.strip()
        if today_name in text:
            capture = True
            continue
        if capture:
            if any(day in text for day in WEEKDAYS.values()):
                break
            if contains_stop(text, stop_after):
                break
            if text:
                items.append(text)
    return clean_menu_items(items)


def parse_makiata_lauttasaari(soup, today_name):
    """Extract only the Lauttasaari section."""
    start = soup.find(lambda tag: tag.name == "p" and "Lauttasaari" in tag.text)
    if not start:
        return "Menu not found"
    items = []
    next_sib = start.find_next_sibling("p")
    while next_sib:
        text = next_sib.text.strip()
        if any(x in text for x in ["Haaga", "Espoo", "Otaniemi"]):
            break
        if any(day in text for day in WEEKDAYS.values()):
            break
        if text:
            items.append(text)
        next_sib = next_sib.find_next_sibling("p")
    return clean_menu_items(items)


# -----------------------------------
# FETCH MENU LOGIC
# -----------------------------------

def fetch_today_menu(restaurant, today_name):
    html = fetch_html(restaurant["url"])
    soup = BeautifulSoup(html, "html.parser")
    type_ = restaurant["type"]
    url = restaurant["url"].lower()

    if "makiata" in url:
        return parse_makiata_lauttasaari(soup, today_name)
    if "persilja" in url:
        return parse_div_snippet(soup, today_name, stop_after=["ERIKOIS", "ERIKOIS LOUNAS"])
    if "pisara" in url:
        return parse_simple_p(soup, today_name, stop_after=["LISÄTIETOJA", "ALLERGEENEISTA"])

    if type_ == "table":
        return parse_table_menu(soup, today_name)
    elif type_ == "list":
        return parse_list_menu(soup, today_name)
    elif type_ == "div_snippet":
        return parse_div_snippet(soup, today_name)
    elif type_ == "simple_p":
        return parse_simple_p(soup, today_name)
    else:
        return "Menu type unknown"


# -----------------------------------
# FEED GENERATION
# -----------------------------------

def build_feed():
    feed = []
    for r in restaurants:
        menu = fetch_today_menu(r, today_name)
        feed.append({
            "name": r["name"],
            "hours": r["hours"],
            "prices": r["prices"],
            "menu": menu
        })
    return feed


def save_feed(feed):
    """Write both README.md and feed.xml files."""
    date_str = datetime.today().strftime("%d.%m.%Y")

    # --- README.md ---
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(f"# 🍽️ Lauttasaari Lunch Menus — {date_str}\n\n")
        f.write(f"### {today_name}\n\n")
        for item in feed:
            f.write(f"## {item['name']}\n")
            f.write(f"**Opening hours:** {item['hours']}\n\n")
            f.write("**Prices:**\n")
            for k, v in item["prices"].items():
                f.write(f"- {k}: {v}\n")
            f.write(f"\n**{today_name} menu:**\n{item['menu']}\n\n---\n\n")

    # --- feed.xml ---
    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<lunchFeed>\n")
        f.write(f"  <date>{html.escape(date_str)}</date>\n")
        f.write(f"  <day>{html.escape(today_name)}</day>\n")
        for item in feed:
            f.write("  <restaurant>\n")
            f.write(f"    <name>{html.escape(item['name'])}</name>\n")
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
