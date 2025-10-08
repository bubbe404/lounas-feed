from playwright.sync_api import sync_playwright
from feedgen.feed import FeedGenerator
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

# Helsinki timezone (automatic DST)
HELSINKI = ZoneInfo("Europe/Helsinki")

today = datetime.now(HELSINKI)
today_str = today.strftime("%A %d.%m.%Y")

restaurants = {
    "Casa Mare": "https://www.ravintolacasamare.com/lounas/",
    "Makiata (Lauttasaari)": "https://www.makiata.fi/lounas/",
    "Pisara": "https://ravintolapisara.fi/lounaslistat/lauttasaari/",
    "Persilja": "https://www.ravintolapersilja.fi/lounas",
    "Bistro Telakka": "https://www.bistrotelakka.fi"
}

fg = FeedGenerator()
fg.id("https://bubbe404.github.io/lounas-feed")
fg.title(f"Lauttasaari Lunch Feed – {today_str}")
fg.link(href="https://bubbe404.github.io", rel="alternate")
fg.description("Päivän lounaslistat Lauttasaaresta")
fg.language("fi")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    for name, url in restaurants.items():
        menu_text = "Ei saatavilla"
        try:
            page.goto(url, timeout=15000)
            page.wait_for_timeout(4000)  # wait 4s for JS to render

            # Extract menu text based on site
            if "casamare" in url:
                el = page.query_selector(".elementor-widget-theme-post-content")
                menu_text = el.inner_text() if el else "Ei saatavilla"

            elif "makiata" in url:
                headers = page.query_selector_all("h2")
                for h in headers:
                    if "Lauttasaari" in h.inner_text():
                        sib = h.evaluate_handle("el => el.nextElementSibling")
                        if sib:
                            menu_text = sib.inner_text() or "Ei saatavilla"
                        break

            elif "pisara" in url:
                el = page.query_selector(".entry-content")
                menu_text = el.inner_text() if el else "Ei saatavilla"

            elif "persilja" in url:
                el = page.query_selector(".elementor-widget-theme-post-content")
                menu_text = el.inner_text() if el else "Ei saatavilla"

            elif "telakka" in url:
                el = page.query_selector("body")
                menu_text = el.inner_text() if el else "Ei saatavilla"

        except Exception as e:
            menu_text = f"Virhe haettaessa: {e}"

        html_desc = f"<b>{name}</b><br>{menu_text.replace(chr(10), '<br>')}"
        entry = fg.add_entry()
        entry.id(url)
        entry.title(f"{name} – {today_str}")
        entry.link(href=url)
        entry.content(content=html_desc, type="html")
        entry.pubDate(datetime.now(HELSINKI))  # timezone-aware

    browser.close()

fg.rss_file("./lounas_feed.xml")
print("✅ RSS feed generated successfully (Helsinki time with DST, safe for GitHub Actions)")
