#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
from feedgen.feed import FeedGenerator

# ---------- CONFIG ----------
RESTAURANTS = [
    {
        "name": "Makiata Lauttasaari",
        "url": "https://makiata.example.com/menu",  # replace with real URL
    },
    {
        "name": "Persilja",
        "url": "https://persilja.example.com/menu",
    },
    {
        "name": "Pisara",
        "url": "https://pisara.example.com/menu",
    },
    {
        "name": "Bistro Telakka",
        "url": "https://telakka.example.com/menu",
    },
    {
        "name": "Casa Mare",
        "url": "https://casamare.example.com/menu",
    }
]

TEST_MODE = False  # True = print today’s menu instead of writing RSS

# ---------- HELPERS ----------

def fetch_html(url):
    """Fetch HTML content of the page."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.text

def parse_menu(restaurant_name, html):
    """Parse today’s menu from restaurant HTML."""
    soup = BeautifulSoup(html, "html.parser")
    today_str = datetime.today().strftime("%A")
    menu_lines = []

    # Attempt to find opening hours and prices
    opening_hours = ""
    prices = ""
    oh_tag = soup.find(text=lambda t: t and "klo" in t)
    if oh_tag:
        opening_hours = oh_tag.strip()
    price_tag = soup.find(text=lambda t: t and "€" in t)
    if price_tag:
        prices = price_tag.strip()

    # Find menu by today
    # For Makiata, example: <tr><td><strong>Maanantai</strong></td><td>...</td></tr>
    day_map = {
        "Monday": ["maanantai", "ma"],
        "Tuesday": ["tiistai", "ti"],
        "Wednesday": ["keskiviikko", "ke"],
        "Thursday": ["torstai", "to"],
        "Friday": ["perjantai", "pe"],
    }
    today_keywords = day_map.get(today_str, [])

    # Search table rows
    rows = soup.find_all("tr")
    for row in rows:
        day_cell = row.find("td")
        menu_cell = row.find_all("td")[1] if len(row.find_all("td")) > 1 else None
        if day_cell and menu_cell:
            day_text = day_cell.get_text(strip=True).lower()
            if any(k in day_text for k in today_keywords):
                dishes = menu_cell.get_text("\n", strip=True).split("\n")
                menu_lines.extend(dishes)

    # Fallback if no table found: search headings with today keywords
    if not menu_lines:
        for kw in today_keywords:
            sections = soup.find_all(text=lambda t: t and kw in t.lower())
            for sec in sections:
                parent = sec.parent
                if parent:
                    next_sibs = parent.find_next_siblings()
                    for sib in next_sibs:
                        texts = sib.get_text("\n", strip=True).split("\n")
                        menu_lines.extend(texts)
                        if len(menu_lines) > 0:
                            break
                if len(menu_lines) > 0:
                    break

    # Filter empty lines
    menu_lines = [line for line in menu_lines if line.strip()]
    return {
        "name": restaurant_name,
        "opening_hours": opening_hours,
        "prices": prices,
        "menu_lines": menu_lines or ["Menu not available today."]
    }

def build_feed():
    fg = FeedGenerator()
    fg.title("Lauttasaari Lunch Feed")
    fg.link(href="https://github.com/bubbe404/lounas-feed", rel="self")
    fg.description("Today’s lunch menus (generated automatically)")

    all_menus = []
    for r in RESTAURANTS:
        html = fetch_html(r["url"])
        parsed = parse_menu(r["name"], html)
        all_menus.append(parsed)

        # Add to RSS
        fe = fg.add_entry()
        fe.title(parsed["name"])
        content = f"Opening hours: {parsed['opening_hours']}\nPrices: {parsed['prices']}\n\n"
        for line in parsed["menu_lines"]:
            content += f"• {line}\n"
        fe.content(content)
        fe.pubDate(datetime.utcnow())

    # Write RSS feed
    fg.rss_file("lounas_feed.xml")

    # Update README
    with open("README.md", "w", encoding="utf-8") as f:
        f.write("# Lauttasaari Lunch Feed\n\n")
        f.write("Today’s lunch menus (generated automatically):\n\n")
        f.write(f"(Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})\n\n")
        for parsed in all_menus:
            f.write(f"### {parsed['name']}\n")
            f.write(f"Opening hours: {parsed['opening_hours']}\n")
            f.write(f"Prices: {parsed['prices']}\n")
            for line in parsed["menu_lines"]:
                f.write(f"• {line}\n")
            f.write("\n")

    if TEST_MODE:
        print("Test mode enabled. Today’s menus:")
        for parsed in all_menus:
            print(f"\n{parsed['name']}")
            print(f"Opening hours: {parsed['opening_hours']}")
            print(f"Prices: {parsed['prices']}")
            for line in parsed["menu_lines"]:
                print(f"• {line}")

if __name__ == "__main__":
    build_feed()
