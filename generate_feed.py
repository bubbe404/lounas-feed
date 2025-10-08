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
    text_lower = text.lower()
    pattern = rf"{weekday_fi}.*?(?={"|".join(WEEKDAYS[today.weekday()+1:])}|$)"
    match = re.search(pattern, text_lower, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()

def scrape_casa_mare():
    url = "https://www.ravintolacasamare.com/lounas/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    content = soup.select_one(".elementor-widget-theme-post-content")
    return extract_today_from_text(content.get_text("\n", strip=True)) if content else "No menu found."

def scrape_makiata():
    url = "https://www.makiata.fi/lounas/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    laut_div = soup.find(lambda tag: tag.name == "h2" and "Lauttasaari" in tag.text)
    if not laut_div:
        return "No Lauttasaari section found."
    parts = []
    for sib in laut_div.find_all_next(["p", "ul"], limit=20):
        if sib.name == "h2":
            break
        parts.append(sib.get_text(" ", strip=True))
    text = "\n".join(parts)
    return extract_today_from_text(text)

def scrape_pisara():
    url = "https://ravintolapisara.fi/lounaslistat/lauttasaari/"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    menu = soup.select_one(".entry-content")
    return extract_today_from_text(menu.get_text("\n", strip=True)) if menu else "No menu found."

def scrape_persilja():
    url = "https://www.ravintolapersilja.fi/lounas"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    menu = soup.select_one(".elementor-widget-theme-post-content")
    return extract_today_from_text(menu.get_text("\n", strip=True)) if menu else "No menu found."

def scrape_telakka():
    url = "https://www.bistrotelakka.fi"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    section = soup.find(string=lambda t: t and "lounas" in t.lower())
    return section.strip() if section else "No menu found."

restaurants = {
    "Casa Mare": ("https://www.ravintolacasamare.com/lounas/", scrape_casa_mare),
    "Makiata (Lauttasaari)": ("https://www.makiata.fi/lounas/", scrape_makiata),
    "Pisara": ("https://ravintolapisara.fi/lounaslistat/lauttasaari/", scrape_pisara),
    "Persilja": ("https://www.ravintolapersilja.fi/lounas", scrape_persilja),
    "Bistro Telakka": ("https://www.bistrotelakka.fi", scrape_telakka),
}

fg = FeedGenerator()
fg.id('https://yourusername.github.io/lounas-feed')
fg.title(f'Lauttasaari Lunch Feed – {today.strftime("%A %d.%m.%Y")}')
fg.link(href='https://yourusername.github.io', rel='alternate')
fg.description('Päivän lounaslistat Lauttasaaresta')
fg.language('fi')

for name, (url, scraper) in restaurants.items():
    try:
        menu_text = scraper()
    except Exception as e:
        menu_text = f"Virhe haettaessa ({name}): {e}"
    html_desc = f"<b>{name}</b><br>{menu_text.replace('\n', '<br>')}"
    entry = fg.add_entry()
    entry.id(url)
    entry.title(f"{name} – {today.strftime('%A')}")
    entry.link(href=url)
    entry.content(content=html_desc, type='html')
    entry.pubDate(datetime.now())

fg.rss_file("lounas_feed.xml")
print("✅ RSS feed generated for today's menus!")
