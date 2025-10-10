# generate_feed.py

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from restaurants import restaurants

WEEKDAYS = {
    0: "Maanantai",
    1: "Tiistai",
    2: "Keskiviikko",
    3: "Torstai",
    4: "Perjantai"
}

today_index = datetime.today().weekday()
today_name = WEEKDAYS.get(today_index, "")


def fetch_html(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def clean_menu_text(text):
    """Cleans up text and formats as bullet list."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "• " + "\n• ".join(lines)


def parse_table_menu(soup, today_name):
    table = soup.find("table", class_="lunch-list-table")
    if not table:
        return "Menu not found"
    for row in table.find_all("tr"):
        if today_name in row.text:
            return clean_menu_text(row.find_all("td")[1].text)
    return "Menu not found"


def parse_list_menu(soup, today_name):
    for li in soup.find_all("li", class_="menu-group-item"):
        if today_name.lower() in li.text.lower():
            items = [p.text.strip() for p in li.find_all("p") if p.text.strip()]
            return clean_menu_text("\n".join(items))
    return "Menu not found"


def parse_div_snippet(soup, today_name, stop_after=None):
    """Used for restaurants like Persilja, Casa Mare."""
    for p in soup.find_all("p"):
        if today_name in p.text:
            items = []
            next_sib = p.find_next_sibling("p")
            while next_sib and not any(day in next_sib.text for day in WEEKDAYS.values()):
                text = next_sib.text.strip()
                if not text:
                    next_sib = next_sib.find_next_sibling("p")
                    continue
                # Stop before irrelevant sections
                if stop_after and any(stop.lower() in text.lower() for stop in stop_after):
                    break
                items.append(text)
                next_sib = next_sib.find_next_sibling("p")
            return clean_menu_text("\n".join(items))
    return "Menu not found"


def parse_simple_p(soup, today_name, stop_after=None):
    """Used for restaurants like Pisara."""
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
            if stop_after and any(stop.lower() in text.lower() for stop in stop_after):
                break
            if text:
                items.append(text)
    return clean_menu_text("\n".join(items)) if items else "Menu not found"


def fetch_today_menu(restaurant, today_name):
    html = fetch_html(restaurant["url"])
    soup = BeautifulSoup(html, "html.parser")
    type_ = restaurant["type"]

    # Handle special cases
    if "persilja" in restaurant["url"]:
        return parse_div_snippet(soup, today_name, stop_after=["à la carte", "A la carte"])
    if "pisara" in restaurant["url"]:
        return parse_simple_p(soup, today_name, stop_after=["Lisätietoja allergeeneista"])
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


def update_feed():
    feed = build_feed()
    for item in feed:
        print(f"--- {item['name']} ---")
        print(f"Opening hours: {item['hours']}")
        print("Prices:")
        for k, v in item["prices"].items():
            print(f"  {k}: {v}")
        print(f"{today_name} menu:\n{item['menu']}\n")


if __name__ == "__main__":
    update_feed()