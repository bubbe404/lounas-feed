from playwright.sync_api import sync_playwright
from feedgen.feed import FeedGenerator
from datetime import datetime
from zoneinfo import ZoneInfo
import re

# Finnish weekday map
WEEKDAYS_FI = {
    0: "maanantai",
    1: "tiistai",
    2: "keskiviikko",
    3: "torstai",
    4: "perjantai",
}

HELSINKI = ZoneInfo("Europe/Helsinki")
today = datetime.now(HELSINKI)
today_str = today.strftime("%A %d.%m.%Y")
today_fi = WEEKDAYS_FI[today.weekday()]

# URLs
restaurants = {
    "Casa Mare": "https://www.ravintolacasamare.com/lounas/",
    "Makiata (Lauttasaari)": "https://www.makiata.fi/lounas/",
    "Pisara": "https://ravintolapisara.fi/lounaslistat/lauttasaari/",
    "Persilja": "https://www.ravintolapersilja.fi/lounas",
    "Bistro Telakka": "https://www.bistrotelakka.fi"
}

def extract_today_menu(text):
    """Extract menu for today using Finnish weekday headings."""
    pattern = rf"{today_fi}.*?(?=(maanantai|tiistai|keskiviikko|torstai|perjantai|$))"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(0).strip() if match else None

fg = FeedGenerator()
fg.id("https://bubbe404.github.io/lounas-feed")
fg.title(f"Lauttasaari Lunch Feed – {today_str}")
fg.link(href="https://bubbe404.github.io/lounas-feed/", rel="alternate")
fg.description("Päivän lounaslistat Lauttasaaresta")
fg.language("fi")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for name, url in restaurants.items():
        menu_text = "Ei saatavilla"
        try:
            page.goto(url, timeout=15000)
            page.wait_for_timeout(4000)  # wait for JS render

            if "makiata" in url:
                # Only Lauttasaari section
                html = page.inner_html("body")
                match = re.search(r"Lauttasaari(.*?)Haaga", html, re.DOTALL | re.IGNORECASE)
                if match:
                    menu_text = extract_today_menu(match.group(1))
            else:
                text = page.inner_text("body")
                menu_text = extract_today_menu(text)

            if not menu_text:
                menu_text = "Ei saatavilla"

        except Exception as e:
            menu_text = f"Virhe haettaessa: {e}"

        html_desc = f"<b>{name}</b><br>{menu_text.replace(chr(10), '<br>')}"
        entry = fg.add_entry()
        entry.id(url)
        entry.title(f"{name} – {today_str}")
        entry.link(href=url)
        entry.content(content=html_desc, type="html")
        entry.pubDate(datetime.now(HELSINKI))

    browser.close()

fg.rss_file("./lounas_feed.xml")
print("✅ RSS feed generated successfully (today's menus only)")
