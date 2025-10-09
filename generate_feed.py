# generate_feed.py
from datetime import datetime
from feedgen.feed import FeedGenerator
from playwright.sync_api import sync_playwright

import datetime as dt

# Define restaurants and URLs
restaurants = [
    {
        "name": "Casa Mare",
        "url": "https://www.ravintolacasamare.com/lounas/",
        "selector": ".lunch-day",  # adjust to actual selector
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Makiata Lauttasaari",
        "url": "https://www.makiata.fi/lounas/",
        "selector": ".lunch-list",  # adjust selector
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Pisara",
        "url": "https://ravintolapisara.fi/lounaslistat/lauttasaari/",
        "selector": ".menu-day",  # adjust selector
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Persilja",
        "url": "https://www.ravintolapersilja.fi/lounas",
        "selector": ".daily-menu",  # adjust selector
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Bistro Telakka",
        "url": "https://www.bistrotelakka.fi",
        "selector": ".lunch-menu",  # adjust selector
        "hours": "Mon–Fri 11:00–14:00"
    },
]

today_weekday = dt.datetime.now().strftime("%A")  # 'Monday', 'Tuesday', etc.

# Initialize RSS feed
fg = FeedGenerator()
fg.title("Lauttasaari Lunch Feed")
fg.link(href="https://bubbe404.github.io/lounas-feed/lounas_feed.xml")
fg.description("Daily lunch menus for Lauttasaari restaurants")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for rest in restaurants:
        page.goto(rest["url"])
        page.wait_for_load_state("domcontentloaded")

        menu_text = "Menu not available today."

        try:
            if rest["name"] == "Casa Mare":
                # Grab only today’s menu
                day_selector = f'div.lunch-day[data-day="{today_weekday}"]'
                day_el = page.query_selector(day_selector)
                if day_el:
                    menu_text = day_el.inner_html()
            else:
                # Other restaurants
                menu_el = page.query_selector(rest["selector"])
                if menu_el:
                    menu_text = menu_el.inner_html()
        except Exception:
            menu_text = "Menu not available today."

        # Add RSS entry
        entry = fg.add_entry()
        entry.title(rest["name"])
        description = f"<b>Opening hours:</b> {rest['hours']}<br>{menu_text}"
        entry.description(description)
        entry.pubDate(datetime.now(tz=datetime.utcnow().astimezone().tzinfo))

    browser.close()

# Save RSS feed
fg.rss_file("./lounas_feed.xml")
print("✅ RSS feed generated successfully.")
