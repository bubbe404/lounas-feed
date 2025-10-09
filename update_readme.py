# update_readme.py
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

def main():
    rss_path = "./lounas_feed.xml"
    readme_path = "./README.md"

    header = "# Lauttasaari Lunch Feed\n\n"
    header += "Today's lunch menus (generated automatically):\n\n"
    header += "[![RSS Feed](https://img.shields.io/badge/RSS-Lounas%20Feed-orange)](https://bubbe404.github.io/lounas-feed/lounas_feed.xml)\n\n"

    try:
        tree = ET.parse(rss_path)
        root = tree.getroot()
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else []
    except Exception as e:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(f"\n*(Error reading feed: {e})*\n")
        return

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(f"*(Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})*\n\n")

        for item in items:
            title_el = item.find("title")
            desc_el = item.find("description")
            title = title_el.text if title_el is not None else "No title"
            desc = desc_el.text if desc_el is not None else ""

            # Extract opening hours
            if "<b>Opening hours:</b>" in desc:
                parts = desc.split("<br>", 1)
                hours_line = parts[0].replace("<b>Opening hours:</b>", "").strip()
                menu_lines = parts[1] if len(parts) > 1 else ""
            else:
                hours_line = ""
                menu_lines = desc

            # Markdown formatting
            menu_lines = menu_lines.replace("<br>", "\n")
            menu_lines = menu_lines.strip().splitlines()
            menu_lines = [line.strip() for line in menu_lines if line.strip()]

            f.write(f"## {title}\n\n")
            if hours_line:
                f.write(f"**Opening hours:** {hours_line}\n\n")
            for line in menu_lines:
                f.write(f"- {line}\n")
            f.write("\n")

if __name__ == "__main__":
    main()
