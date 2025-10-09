# update_readme.py
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import html

def main():
    rss_path = "./lounas_feed.xml"
    readme_path = "./README.md"

    header_lines = [
        "# Lauttasaari Lunch Feed",
        "",
        "Today's lunch menus (generated automatically):",
        "",
        "[![RSS Feed](https://img.shields.io/badge/RSS-Lounas%20Feed-orange)](https://bubbe404.github.io/lounas-feed/lounas_feed.xml)",
        "",
    ]

    try:
        tree = ET.parse(rss_path)
        root = tree.getroot()
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else []
    except Exception as e:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("\n".join(header_lines) + "\n\n")
            f.write(f"*(Error reading feed: {e})*\n")
        return

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header_lines) + "\n")
        f.write(f"*(Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')})*\n\n")

        for item in items:
            title_el = item.find("title")
            desc_el = item.find("description")
            title = title_el.text if title_el is not None else "No title"
            desc = desc_el.text if desc_el is not None else ""

            # description is HTML with <br> separators and a leading "Opening hours" element
            # Convert HTML escapes
            desc = html.unescape(desc)

            # Extract opening hours if present (pattern "<b>Opening hours:</b> ...<br>")
            hours = ""
            menu_html = desc
            hours_match = None
            if "<b>Opening hours:</b>" in desc:
                # split on first <br>
                parts = desc.split("<br>", 1)
                hours_part = parts[0].replace("<b>Opening hours:</b>", "").strip()
                hours = hours_part
                menu_html = parts[1] if len(parts) > 1 else ""

            # Convert <br> to lines
            menu_text = menu_html.replace("<br>", "\n")
            # Remove any stray tags
            menu_text = re.sub(r"<[^>]+>", "", menu_text)

            lines = [ln.strip() for ln in menu_text.splitlines() if ln.strip()]

            # Write
            f.write(f"## {title}\n\n")
            if hours:
                f.write(f"**Opening hours:** {hours}\n\n")
            if lines:
                for ln in lines:
                    f.write(f"- {ln}\n")
            else:
                f.write("- Menu not available today.\n")
            f.write("\n")

if __name__ == "__main__":
    import re
    main()
