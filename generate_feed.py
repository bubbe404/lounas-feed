# generate_feed.py
from datetime import datetime
from feedgen.feed import FeedGenerator
from playwright.sync_api import sync_playwright
import datetime as dt

# Define restaurants
restaurants = [
    {
        "name": "Casa Mare",
        "url": "https://www.ravintolacasamare.com/lounas/",
        "day_selector": 'div.lunch-day',  # adjust based on HTML
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Makiata Lauttasaari",
        "url": "https://www.makiata.fi/lounas/",
        "day_selector": '.lunch-list',
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Pisara",
        "url": "https://ravintolapisara.fi/lounaslistat/lauttasaari/",
        "day_selector": '.menu-day',
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Persilja",
        "url": "https://www.ravintolapersilja.fi/lounas",
        "day_selector": '.daily-menu',
        "hours": "Mon–Fri 11:00–14:00"
    },
    {
        "name": "Bistro Telakka",
        "url": "https://www.bistrotelakka.fi",
        "day_selector": '.lunch-menu',
        "hours": "Mon–Fri 11:00–14:00"
    },
]

today_weekday = dt.datetime.now().strftime("%A")  # 'Monday', 'Tuesday', etc.

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
                # For Casa Mare, find today's menu based on weekday
                day_elements = page.query_selector_all(rest["day_selector"])
                menu_items = []
                for el in day_elements:
                    # Some sites have data-day or headings, adjust as needed
                    heading = el.query_selector("h3")
                    if heading and today_weekday.lower() in heading.inner_text().lower():
                        # Extract <li> or <p> only
                        dish_elements = el.query_selector_all("li, p")
                        menu_items = [d.inner_text().strip() for d in dish_elements if d.inner_text().strip()]
                        break
                if menu_items:
                    menu_text = "<br>".join(menu_items)
            else:
                # Other restaurants
                container = page.query_selector(rest["day_selector"])
                if container:
                    dish_elements = container.query_selector_all("li, p")
                    menu_items = [d.inner_text().strip() for d in dish_elements if d.inner_text().strip()]
                    if menu_items:
                        menu_text = "<br>".join(menu_items)
        except Exception:
            menu_text = "Menu not available today."

        # Add RSS entry
        entry = fg.add_entry()
        entry.title(rest["name"])
        description = f"<b>Opening hours:</b> {rest['hours']}<br>{menu_text}"
        entry.description(description)
        entry.pubDate(datetime.now(tz=datetime.utcnow().astimezone().tzinfo))

    browser.close()

# Save RSS
fg.rss_file("./lounas_feed.xml")
print("✅ RSS feed generated successfully.")
