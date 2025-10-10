# generate_feed.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
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
    """Format items into Markdown bullets with proper line breaks.
    Each bullet ends with two spaces + newline so Markdown renders a line break.
    """
    cleaned = [line.strip() for line in items if line and line.strip()]
    if not cleaned:
        return "Menu not found"
    return "".join(f"• {line}  \n" for line in cleaned)


def contains_stop(text, stop_after):
    """Case-insensitive stop word check."""
    if not text or not stop_after:
        return False
    lower_text = text.lower()
    return any(stop.lower() in lower_text for stop in stop_after)


def first_stop_index(text, stop_after):
    """Return earliest index where any stop word appears (case-insensitive), or -1."""
    lower_text = text.lower()
    idxs = [lower_text.find(stop.lower()) for stop in (stop_after or []) if lower_text.find(stop.lower()) != -1]
    return min(idxs) if idxs else -1


def parse_date_range_from_text(text):
    """Try to extract a start/end date from texts like '6.10.-10.10.2025' or '6.10. - 10.10.2025'."""
    # Extract all numbers
    nums = re.findall(r"\d+", text)
    try:
        if len(nums) >= 5:
            sd, sm, ed, em, ey = map(int, nums[:5])
            start = date(ey, sm, sd)
            end = date(ey, em, ed)
            return start, end
    except Exception:
        pass
    return None, None


# -----------------------------------
# PARSERS
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
            # split on commas and newlines to get items
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
    """Scan siblings of the <p> that contains the weekday; stop on any element containing stop keywords."""
    for p in soup.find_all():
        # consider any tag as candidate; but usually it's <p> with weekday
        if p.name and today_name in p.get_text(" ", strip=True):
            items = []
            sib = p.find_next_sibling()
            while sib:
                text = sib.get_text(" ", strip=True)
                if not text:
                    sib = sib.find_next_sibling()
                    continue
                # stop if next weekday header encountered
                if any(day in text for day in WEEKDAYS.values()):
                    break
                # stop if stop word appears in this sibling; if so, append the portion before stop
                if stop_after and contains_stop(text, stop_after):
                    idx = first_stop_index(text, stop_after)
                    if idx and idx > 0:
                        prefix = text[:idx].strip()
                        if prefix:
                            items.append(prefix)
                    break
                items.append(text)
                sib = sib.find_next_sibling()
            return clean_menu_items(items)
    return "Menu not found"


def parse_simple_p(soup, today_name, stop_after=None):
    """Iterate through <p> tags; handle stop words in same <p> by trimming text before the stop word."""
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
                if idx and idx > 0:
                    prefix = text[:idx].strip()
                    if prefix:
                        items.append(prefix)
                break
            items.append(text)
    return clean_menu_items(items)


# -----------------------------------
# Makiata special
# -----------------------------------

def parse_makiata_lauttasaari(soup):
    """Prefer table parsing, but only if the table's date-range includes today.
       If no date range is present, attempt to find the table row for today's weekday.
    """
    # 1) Try to find header that mentions Lauttasaari and nearest small with date range
    header = soup.find(lambda tag: tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]
                       and "lauttasaari" in tag.get_text(" ", strip=True).lower())
    small_text = None
    if header:
        small = header.find("small")
        if not small:
            small = header.find_next("small")
        if small:
            small_text = small.get_text(" ", strip=True)

    # 2) Try to find the table
    table = soup.find("table", class_="lunch-list-table")
    if table:
        # If we found a date range, check it
        if small_text:
            start, end = parse_date_range_from_text(small_text)
            if start and end:
                today_dt = date.today()
                if not (start <= today_dt <= end):
                    # We won't use the table because it is for another week
                    return "Menu not found"
                # otherwise proceed to parse the table for today's weekday
        # parse table rows for today's weekday regardless
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if not cols:
                continue
            day_text = cols[0].get_text(" ", strip=True)
            if today_name.lower() in day_text.lower():
                menu_text = cols[1].get_text(separator="\n", strip=True)
                items = [it.strip() for part in re.split(r"\n|,", menu_text) for it in [part] if it.strip()]
                return clean_menu_items(items)
    # fallback: try to find a Lauttasaari paragraph block (older structure)
    if header:
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
# DISPATCHER
# -----------------------------------

def fetch_today_menu(restaurant, today_name):
    html_text = fetch_html(restaurant["url"])
    soup = BeautifulSoup(html_text, "html.parser")
    type_ = restaurant.get("type", "")
    url = restaurant["url"].lower()

    # restaurant-specific rules
    if "makiata" in url:
        return parse_makiata_lauttasaari(soup)

    if "persilja" in url:
        # stop on any ERIKOIS* section (case-insensitive)
        return parse_div_snippet(soup, today_name, stop_after=["ERIKOIS", "ERIKOIS LOUNAS", "ERIKOISLOUNAS", "ERIKOIS ANNOS"])

    if "pisara" in url:
        return parse_simple_p(soup, today_name, stop_after=["LISÄTIETOJA", "ALLERGEENEISTA"])

    # fallback by declared type
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
            # row break before bullets
            f.write(f"**{today_name} menu:**\n\n")
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