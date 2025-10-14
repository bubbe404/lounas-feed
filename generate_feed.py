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


def parse_table_menu(soup, today_name):
    table = soup.find("table", class_="lunch-list-table")
    if not table:
        return "Menu not found"
    for row in table.find_all("tr"):
        if today_name in row.text:
            return row.find_all("td")[1].text.strip()
    return "Menu not found"


def parse_list_menu(soup, today_name):
    for li in soup.find_all("li", class_="menu-group-item"):
        if today_name.lower() in li.text.lower():
            items = [p.text.strip() for p in li.find_all("p") if p.text.strip()]
            return "\n• " + "\n• ".join(items)
    return "Menu not found"


def parse_div_snippet(soup, today_name):
    for p in soup.find_all("p"):
        if today_name in p.text:
            items = []
            next_sib = p.find_next_sibling("p")
            while next_sib and not any(day in next_sib.text for day in WEEKDAYS.values()):
                if next_sib.text.strip():
                    items.append(next_sib.text.strip())
                next_sib = next_sib.find_next_sibling("p")
            if items:
                return "\n• " + "\n• ".join(items)
    return "Menu not found"


def parse_simple_p(soup, today_name):
    sections = soup.find_all("p")
    capture = False
    items = []
    for p in sections:
        if today_name in p.text:
            capture = True
            continue
        if capture:
            if any(day in p.text for day in WEEKDAYS.values()):
                break
            text = p.text.strip()
            if text:
                items.append(text)
    return ("\n• " + "\n• ".join(items)) if items else "Menu not found"


# --- Fix for Persilja ---
def parse_persilja(soup, today_name):
    """Extract buffet section only, before 'ERIKOISANNOS'"""
    content = soup.get_text("\n", strip=True)
    # find today's section
    start = content.find(today_name)
    if start == -1:
        return "Menu not found"
    section = content[start:]
    # cut at the next uppercase heading like ERIKOISANNOS
    for stopword in ["ERIKOISANNOS", "A LA CARTE", "A LA CARTE"]:
        pos = section.find(stopword)
        if pos != -1:
            section = section[:pos]
    # split into bullets
    lines = [ln.strip() for ln in section.split("\n") if ln.strip() and not ln.startswith(today_name)]
    if not lines:
        return "Menu not found"
    return "\n• " + "\n• ".join(lines)


# --- Fix for Casa Mare ---
def parse_casamare(soup, today_name):
    """Handles Casa Mare structure with <tr> or <div> layout"""
    # try table first
    table = soup.find("table")
    if table:
        for row in table.find_all("tr"):
            if today_name in row.text:
                tds = row.find_all("td")
                if len(tds) > 1:
                    return tds[1].text.strip()
    # fallback: parse divs and paragraphs
    paras = soup.find_all(["p", "div"])
    items = []
    capture = False
    for p in paras:
        text = p.get_text(strip=True)
        if today_name in text:
            capture = True
            continue
        if capture:
            if any(day in text for day in WEEKDAYS.values()):
                break
            if text:
                items.append(text)
    return ("\n• " + "\n• ".join(items)) if items else "Menu not found"


def fetch_today_menu(restaurant, today_name):
    html = fetch_html(restaurant["url"])
    soup = BeautifulSoup(html, "html.parser")
    name = restaurant["name"].lower()
    type_ = restaurant["type"]

    # Use special parsers for Persilja & Casa Mare
    if "persilja" in name:
        return parse_persilja(soup, today_name)
    elif "casa" in name:
        return parse_casamare(soup, today_name)

    # Everything else unchanged
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