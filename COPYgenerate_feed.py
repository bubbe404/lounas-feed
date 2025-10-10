import requests
from bs4 import BeautifulSoup
from datetime import datetime
from restaurants import restaurants
import xml.etree.ElementTree as ET

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
    """Download HTML from the given restaurant URL."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text

def parse_table_menu(soup, today_name):
    table = soup.find("table", class_="lunch-list-table")
    if not table:
        return "Menu not found"
    for row in table.find_all("tr"):
        if today_name in row.text:
            tds = row.find_all("td")
            if len(tds) > 1:
                return tds[1].text.strip()
    return "Menu not found"

def parse_list_menu(soup, today_name):
    for li in soup.find_all("li", class_="menu-group-item"):
        if today_name.lower() in li.text.lower():
            items = [p.text.strip() for p in li.find_all("p") if p.text.strip()]
            return "\n".join(items)
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
            return "\n".join(items)
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
            if p.text.strip():
                items.append(p.text.strip())
    return "\n".join(items) if items else "Menu not found"

def fetch_today_menu(restaurant, today_name):
    """Fetch and parse the restaurant's menu for today."""
    try:
        html = fetch_html(restaurant["url"])
        soup = BeautifulSoup(html, "html.parser")
        type_ = restaurant["type"]

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
    except Exception as e:
        print(f"⚠️ Error fetching {restaurant['name']}: {e}")
        return "Menu not found"

def build_feed():
    """Build a list of restaurants and their menus."""
    feed = []
    for r in restaurants:
        menu = fetch_today_menu(r, today_name)
        if menu != "Menu not found":
            feed.append({
                "name": r["name"],
                "hours": r["hours"],
                "prices": r["prices"],
                "menu": menu
            })
        else:
            print(f"ℹ️ Skipping {r['name']} (no menu found for {today_name})")
    return feed

def save_feed_xml(feed):
    """Save feed to feed.xml."""
    root = ET.Element("restaurants")
    for item in feed:
        rest_el = ET.SubElement(root, "restaurant", name=item["name"])
        ET.SubElement(rest_el, "hours").text = item["hours"]
        prices_el = ET.SubElement(rest_el, "prices")
        for k, v in item["prices"].items():
            ET.SubElement(prices_el, "price", type=k).text = v
        ET.SubElement(rest_el, "menu", day=today_name).text = item["menu"]

    tree = ET.ElementTree(root)
    tree.write("feed.xml", encoding="utf-8", xml_declaration=True)
    print("✅ feed.xml saved successfully")

def save_readme(feed):
    """Generate a readable Markdown summary of today’s menus."""
    lines = [
        "# 🍽️ Lunch Menus for Today\n",
        f"**Date:** {datetime.today().strftime('%A, %d %B %Y')} ({today_name})\n"
    ]
    for item in feed:
        lines.append(f"## {item['name']}\n")
        lines.append(f"**Opening hours:** {item['hours']}\n")
        lines.append("**Prices:**")
        for k, v in item["prices"].items():
            lines.append(f"- {k}: {v}")
        lines.append("\n**Today's Menu:**\n")
        lines.append(f"{item['menu']}\n")
        lines.append("---\n")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("✅ README.md updated successfully")

def update_feed():
    print("⏳ Building today's feed...")
    feed = build_feed()
    if not feed:
        print("❌ No menus found for any restaurant today. Skipping file generation.")
        return
    save_feed_xml(feed)
    save_readme(feed)
    print("🎉 Feed generation completed successfully!")

if __name__ == "__main__":
    update_feed()
