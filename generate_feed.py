import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
import re

WEEKDAYS = [
    "maanantai", "tiistai", "keskiviikko",
    "torstai", "perjantai", "lauantai", "sunnuntai"
]

today = datetime.now()
weekday_fi = WEEKDAYS[today.weekday()]

def extract_today_from_text(text):
    if not text:
        return "Ei lounasta löytynyt."
    text_lower = text.lower()
    try:
        pattern = rf"{weekday_fi}.*?(?={"|".join(WEEKDAYS[today.weekday()+1:])}|$)"
        match = re.search(pattern, text_lower, re.DOTALL)
        if match:
            return match.group(0).strip()
        return text.strip()
    except Exception:
        return text.strip()

def safe_scrape(url, selector=None, laut_div_check=False):
    """Fetch page, return today's menu or placeholder"""
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        if laut_div_check:
            laut_div = soup.find(lambda tag: tag.name == "h2" and "Lauttasaari" in tag.text)
            if not laut_div:
                return "Ei lounasta löytynyt."
            parts = []
            for sib in laut_div.find_all_next(["p", "ul"], limit=20):
                if sib.name == "h2":
                    break
                parts.append(sib.get_text(" ", strip=True))
            text = "\n".join(parts)
            return extract_today_from_text(text)
        if selector:
            content = soup.select_one(selector)
            if content:
                return extract_today_from_text(content.get_text("\n", strip=True))
        return "Ei lounasta löytynyt."
    except Exception as e:
        return f"Virhe haettaessa: {e}"

restaurants = {
    "Casa Mare": ("https://www.ravintolacasamare.com/lounas/", ".elementor-widget-theme-post-content", False),
    "Makiata (Lauttasaari)": ("https://www.makiata.fi/lounas/", None, True),
    "Pisara": ("https://ravintolapisara.fi/lounaslistat/lauttasaari/", ".entry-content", False),
    "Persilja": ("https://www.ravintolapersilja.fi/lounas", ".elementor-widget-theme-post-content", False),
    "Bistro Telakka": ("https://www.bistrotelakka.fi", None, False)
}

fg = FeedGenerator()
fg.id('https://bubbe404.github.io/lounas-feed')
fg.title(f'Lauttasaari Lunch Feed – {today.strftime("%A %d.%m.%Y")}')
fg.link(href='https://bubbe404.github.io', rel='alternate')
fg.description('Päivän lounaslistat Lauttasaaresta')
fg.language('fi')

for name, (url, selector, laut_check) in restaurants.items():
    menu_text = safe_scrape(url, selector, laut_check)
    html_desc = f"<b>{name}</b><br>{menu_text.replace(chr(10), '<br>')}"
    entry = fg.add_entry()
    entry.id(url)
    entry.title(f"{name} – {today.strftime('%A')}")
    entry.link(href=url)
    entry.content(content=html_desc, type='html')
    entry.pubDate(datetime.now())

# Always write feed file, even if errors occurred
fg.rss_file("lounas_feed.xml")
print("✅ RSS feed generated (safe version).")
