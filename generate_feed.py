# generate_feed.py
"""
Generate lounas_feed.xml containing today's lunch menus for Lauttasaari restaurants.
This script:
 - uses Playwright to fetch the pages (handles JS)
 - extracts today's menu by finding Finnish weekday headings
 - extracts opening hours heuristically
 - cleans HTML/text to keep only dish lines (preserves prices)
 - writes ./lounas_feed.xml
"""
from playwright.sync_api import sync_playwright
from feedgen.feed import FeedGenerator
from datetime import datetime
from zoneinfo import ZoneInfo
import re
import html

HELSINKI = ZoneInfo("Europe/Helsinki")

# Finnish weekday names (lowercase)
WEEKDAYS_FI = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]
# We'll only use Mon-Fri typically, but regex covers all.

TODAY = datetime.now(HELSINKI)
TODAY_FI = WEEKDAYS_FI[TODAY.weekday()]

# List of restaurants and their URLs. We will try to extract opening hours from page text.
RESTAURANTS = [
    ("Casa Mare", "https://www.ravintolacasamare.com/lounas/"),
    ("Makiata (Lauttasaari)", "https://www.makiata.fi/lounas/"),
    ("Pisara", "https://ravintolapisara.fi/lounaslistat/lauttasaari/"),
    ("Persilja", "https://www.ravintolapersilja.fi/lounas"),
    ("Bistro Telakka", "https://www.bistrotelakka.fi"),
]

# Helper regexes
WEEKDAY_RE = re.compile(r"(maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai)", re.IGNORECASE)
NEXT_DAY_BOUNDARY = re.compile(r"(maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai)", re.IGNORECASE)
DATE_RE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")  # e.g. 8.10.2025

# Heuristics to discard lines that are not dishes
GARBAGE_PATTERNS = [
    re.compile(r"(?i)hinnasto"), re.compile(r"(?i)osoite"), re.compile(r"(?i)kartta"),
    re.compile(r"(?i)vara(a)?( pöytä| pöytää| pöytävaraus)"),
    re.compile(r"(?i)kokeile"), re.compile(r"(?i)keittolounas"), re.compile(r"(?i)lounas arkisin"),
    re.compile(r"(?i)ma–pe"), re.compile(r"(?i)ma-pe"), re.compile(r"(?i)keittiö sulkeutuu"),
    re.compile(r"(?i)henkilö"), re.compile(r"(?i)puhelin"), re.compile(r"(?i)yhteystiedot")
]

def clean_line(line: str) -> str:
    """Clean a single candidate line: unescape HTML, strip whitespace, remove multiple spaces."""
    line = html.unescape(line)
    line = line.strip()
    # Remove stray HTML tags if any remain
    line = re.sub(r"<[^>]+>", "", line)
    # Normalize whitespace
    line = re.sub(r"\s+", " ", line)
    return line

def is_probable_dish(line: str) -> bool:
    """Return True if line looks like a dish (not header/address/price-block)."""
    if not line:
        return False
    low = line.lower()
    # discard if looks like a section heading like 'Hinnasto' or 'Osoite' etc.
    for p in GARBAGE_PATTERNS:
        if p.search(low):
            return False
    # discard lines that look like 'Maanantai 6.10.2025'
    if WEEKDAY_RE.search(low) and DATE_RE.search(low):
        return False
    # discard short noise like single words 'Kahvila' or 'Pohjois-Haaga' unless they contain digits/prices
    if len(line) < 3:
        return False
    # if line is just a single location name without numbers or commas, it's probably not a dish
    if re.match(r"^[A-Za-zÅÄÖåäö\-\s]+$", line) and len(line.split()) <= 2 and not re.search(r"\d", line):
        return False
    return True

def extract_opening_hours(text: str) -> str:
    """Heuristic: find a nearby 'Aukioloajat' or a 'Lounas ... klo' line."""
    # Try to find 'Aukioloajat' block
    m = re.search(r"Aukioloajat(.*?)(?:\n\n|\Z)", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        # return first non-empty line from the block
        block = m.group(1).strip()
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if lines:
            # join first two lines for brevity
            return " / ".join(lines[:2])
    # Fallback: find line containing 'lounas' and a time pattern
    m2 = re.search(r"([^\n]{0,80}lounas[^\n]{0,80})", text, flags=re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    # Another fallback: find 'Ma-Pe' or 'Ma–Pe' lines
    m3 = re.search(r"([^\n]{0,80}ma[\-–]pe[^\n]{0,80})", text, flags=re.IGNORECASE)
    if m3:
        return m3.group(1).strip()
    return ""

def extract_today_menu_from_text(full_text: str, scope_substring: str = None) -> list:
    """
    Extract today's menu lines from the provided text.
    If scope_substring is provided, limit search to that substring (e.g., 'Lauttasaari' section).
    Returns list of cleaned dish lines (strings).
    """
    text = full_text
    if scope_substring:
        idx = text.lower().find(scope_substring.lower())
        if idx != -1:
            # take from idx to maybe next double-newline or till end
            text = text[idx:]
    # Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Find the position of today's weekday
    wd_pattern = re.compile(rf"{TODAY_FI}", re.IGNORECASE)
    m = wd_pattern.search(text)
    if not m:
        # as fallback try to find the date like '8.10.2025' and then use that section
        date_m = DATE_RE.search(text)
        if date_m:
            start = date_m.start()
            snippet = text[start:]
        else:
            snippet = text
    else:
        start = m.start()
        snippet = text[start:]
    # Cut until next weekday heading (so we only keep today's block)
    next_m = NEXT_DAY_BOUNDARY.search(snippet, flags=re.IGNORECASE, pos=1)
    if next_m:
        snippet = snippet[:next_m.start()]
    # Split lines and clean them
    lines = [clean_line(ln) for ln in snippet.splitlines()]
    # Remove obvious header lines like 'Keskiviikko 8.10.2025' or empty lines
    cleaned = []
    for ln in lines:
        if not ln:
            continue
        low = ln.lower()
        if DATE_RE.search(ln):
            # skip date lines
            continue
        # Skip the exact weekday word alone
        if ln.strip().lower() == TODAY_FI:
            continue
        # Skip lines that are clearly separators or headings
        if any(s in low for s in ("#####", "kokoukset", "vara", "varaa", "hinnasto", "osoite", "kartta")):
            continue
        if is_probable_dish(ln):
            cleaned.append(ln)
    # Some sites concatenate day name and menu without a space -> try to split by known weekday words
    # If cleaned is empty, attempt fallback: split snippet by two-newline blocks and pull lines with commas/prices
    if not cleaned:
        candidates = re.split(r"\n{1,3}", snippet)
        for c in candidates:
            c = clean_line(c)
            if is_probable_dish(c):
                # often these blocks contain multiple dishes concatenated; split by comma where appropriate
                parts = [p.strip() for p in re.split(r"\s{2,}|,\s*", c) if p.strip()]
                for p in parts:
                    if is_probable_dish(p):
                        cleaned.append(p)
    # Final dedupe while preserving order
    seen = set()
    final = []
    for c in cleaned:
        if c not in seen:
            final.append(c)
            seen.add(c)
    return final

def build_feed():
    fg = FeedGenerator()
    fg.id("https://bubbe404.github.io/lounas-feed")
    fg.title(f"Lauttasaari Lunch Feed – {TODAY.strftime('%A %d.%m.%Y')}")
    fg.link(href="https://bubbe404.github.io/lounas-feed/", rel="alternate")
    fg.description("Päivän lounaslistat Lauttasaaresta")
    fg.language("fi")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_navigation_timeout(20000)

        for name, url in RESTAURANTS:
            try:
                page.goto(url)
            except Exception as e:
                # network/navigation error
                menu_lines = []
                hours = ""
                description_html = f"<b>Opening hours:</b> {hours}<br>Virhe haettaessa: {e}"
                entry = fg.add_entry()
                entry.id(url)
                entry.title(f"{name} – {TODAY.strftime('%A')}")
                entry.link(href=url)
                entry.content(content=description_html, type="html")
                entry.pubDate(datetime.now(HELSINKI))
                continue

            # get full visible text (Playwright's inner_text on body)
            try:
                body_text = page.inner_text("body")
            except Exception:
                body_text = page.content()
                # fall back to raw HTML if inner_text fails

            # Try to scope for Makiata to Lauttasaari only
            scope = None
            if "makiata" in url:
                scope = "Lauttasaari"

            # Extract opening hours heuristically from page text
            hours = extract_opening_hours(body_text)

            # Extract today's menu lines
            menu_lines = extract_today_menu_from_text(body_text, scope_substring=scope)

            # If empty, try a secondary pass with inner_html and searching for <li> or <p>
            if not menu_lines:
                try:
                    html_blob = page.inner_html("body")
                    # find <li> elements inside area near today's weekday
                    # naive but helpful fallback: extract all <li> under body and keep those near weekday string
                    li_texts = re.findall(r"<li[^>]*>(.*?)</li>", html_blob, flags=re.DOTALL|re.IGNORECASE)
                    # clean and pick those that contain today's weekday or are likely dishes
                    li_clean = [clean_line(html.unescape(re.sub(r"<[^>]+>", "", t))) for t in li_texts]
                    # filter
                    li_clean = [t for t in li_clean if is_probable_dish(t)]
                    if li_clean:
                        menu_lines = li_clean
                except Exception:
                    pass

            # Final fallback: if still empty, look for any lines containing digits (prices) in body_text
            if not menu_lines:
                candidate_lines = [clean_line(x) for x in body_text.splitlines() if x.strip()]
                candidate_lines = [ln for ln in candidate_lines if re.search(r"\d+[.,]\d{2}\s*€|€|\d+,\d{2}", ln)]
                if candidate_lines:
                    menu_lines = candidate_lines[:6]  # take a few

            # Compose HTML description for RSS (keep prices intact, join with <br>)
            if menu_lines:
                safe_html = "<br>".join([html.escape(m) for m in menu_lines])
            else:
                safe_html = "Menu not available today."

            desc_html = f"<b>Opening hours:</b> {html.escape(hours)}<br>{safe_html}"
            entry = fg.add_entry()
            entry.id(url)
            entry.title(f"{name} – {TODAY.strftime('%A')}")
            entry.link(href=url)
            entry.content(content=desc_html, type="html")
            entry.pubDate(datetime.now(HELSINKI))

        browser.close()

    # write to repo root
    fg.rss_file("./lounas_feed.xml")

if __name__ == "__main__":
    build_feed()
    print("✅ RSS feed generated (cleaned, today-only).")
