"""
spike.py - Step 0 technical spike for the Comparative Fiqh Explorer.

A "spike" is a small throwaway experiment that answers questions
BEFORE we design the real code. This one answers four questions:

  1. Does Shamela's robots.txt allow reading book pages?
  2. How big is one page, and how long does one request take?
  3. Where do the main text and the footnotes live inside the HTML?
  4. Does turath.io offer this book as one ready-made file (a big shortcut)?

How to run (inside the project folder):
    pip install requests beautifulsoup4
    python spike.py

Output:
    spike_output/report.txt    -> the summary to send back
    spike_output/*.html        -> raw page samples (send these too)
    spike_output/*.json        -> turath samples, if available
"""

import json
import re
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- settings
BOOK_ID = 9849
TOTAL_PAGES_ESTIMATE = 2230          # 5 volumes, from the book card
SHAMELA = "https://shamela.ws"
TURATH_API = "https://api.turath.io"
TURATH_FILES = "https://files.turath.io"

# Two pages chosen on purpose: each one shows a different writing style.
SAMPLE_PAGES = {
    308: "vol 1 - differences are in the footnotes",
    1837: "vol 5 - differences are inline in the main text",
}

DELAY_SECONDS = 1.5                  # polite pause between requests
OUTPUT_DIR = Path("../spike_output")
HEADERS = {
    "User-Agent": "FiqhExplorer-StudentProject/0.1 "
                  "(university software engineering project)"
}

# Madhab name, then up to 40 characters, then the word "qalu".
# This catches grouped statements too ("Malikiyya, Shafi'iyya ... qalu").
MADHAB_MARKER = re.compile(r"(الحنفية|المالكية|الشافعية|الحنابلة)[^:]{0,40}قالوا")

# Footnote numbers written with Arabic-Indic digits, e.g. (١) (١٢)
FOOTNOTE_MARKER = re.compile(r"\([٠-٩]+\)")

report_lines = []


# ---------------------------------------------------------------- helpers
def log(text=""):
    """Print a line and keep it for report.txt."""
    print(text)
    report_lines.append(str(text))


def fetch(url, params=None, method="GET"):
    """Send one request and measure how long it took."""
    start = time.perf_counter()
    response = requests.request(method, url, params=params,
                                headers=HEADERS, timeout=30)
    elapsed = time.perf_counter() - start
    # If the server does not name its encoding, requests guesses Latin-1,
    # which turns Arabic into garbage. Shamela and turath use UTF-8.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = "utf-8"
    return response, elapsed


def describe(tag):
    """Short CSS-like name for a tag, e.g. div#main.nass.big"""
    name = tag.name
    if tag.get("id"):
        name += "#" + tag["id"]
    classes = tag.get("class", [])
    if classes:
        name += "." + ".".join(classes)
    return name


def path_of(tag, depth=4):
    """Path of the last few ancestors, e.g. div.page > div.nass > p"""
    parts = []
    while tag is not None and tag.name not in ("[document]", "html") \
            and len(parts) < depth:
        parts.append(describe(tag))
        tag = tag.parent
    return " > ".join(reversed(parts))


# ---------------------------------------------------------------- step 1
def check_robots():
    log("=== 1. robots.txt ===")
    response, _ = fetch(f"{SHAMELA}/robots.txt")
    log(f"status: {response.status_code}")
    rules = [line.strip() for line in response.text.splitlines()
             if line.strip().lower().startswith(
                 ("user-agent", "disallow", "allow", "crawl-delay"))]
    for line in rules[:40]:
        log("  " + line)
    if len(rules) > 40:
        log(f"  ... {len(rules) - 40} more rules")
    log()


# ---------------------------------------------------------------- step 2+3
def inspect_page(page_number, label):
    log(f"=== 2/3. page {page_number} ({label}) ===")
    url = f"{SHAMELA}/book/{BOOK_ID}/{page_number}"
    response, elapsed = fetch(url)
    log(f"status: {response.status_code}   time: {elapsed:.2f}s")

    html = response.text
    # Save the exact bytes the server sent, untouched.
    (OUTPUT_DIR / f"page_{page_number}.html").write_bytes(response.content)

    raw_bytes = len(response.content)
    compressed_bytes = len(zlib.compress(response.content, 9))
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    text_bytes = len(visible_text.encode("utf-8"))

    log(f"raw HTML: {raw_bytes / 1024:.1f} KB   "
        f"compressed: {compressed_bytes / 1024:.1f} KB   "
        f"visible text (upper bound): {text_bytes / 1024:.1f} KB")

    # The <title> usually holds volume, printed page and chapter name.
    if soup.title and soup.title.string:
        log("title:")
        log(soup.title.string.strip())

    # Where do the madhab statements live?
    marker_paths = Counter()
    for node in soup.find_all(string=MADHAB_MARKER):
        marker_paths[path_of(node.parent)] += 1
    log(f"madhab markers found: {sum(marker_paths.values())}")
    for path, count in marker_paths.most_common(5):
        log(f"  {count:>3}x  {path}")

    # Where do the footnote numbers live?
    footnote_paths = Counter()
    for node in soup.find_all(string=FOOTNOTE_MARKER):
        footnote_paths[path_of(node.parent)] += 1
    log(f"footnote numbers found: {sum(footnote_paths.values())}")
    for path, count in footnote_paths.most_common(5):
        log(f"  {count:>3}x  {path}")

    # Any containers whose class name hints at text or footnotes?
    hint = re.compile(r"nass|hamesh|footnote|text|content|page", re.I)
    log("candidate containers (class name -> text length):")
    seen = set()
    for tag in soup.find_all(class_=hint):
        key = describe(tag)
        if key in seen:
            continue
        seen.add(key)
        log(f"  {key:<45} {len(tag.get_text(strip=True)):>6} chars")
    log()

    return {"raw": raw_bytes, "compressed": compressed_bytes,
            "text": text_bytes, "seconds": elapsed}


def inspect_index():
    log("=== 3b. book index page ===")
    response, elapsed = fetch(f"{SHAMELA}/book/{BOOK_ID}")
    log(f"status: {response.status_code}   time: {elapsed:.2f}s")
    (OUTPUT_DIR / "index.html").write_bytes(response.content)

    soup = BeautifulSoup(response.text, "html.parser")
    link_pattern = re.compile(rf"/book/{BOOK_ID}/(\d+)")
    pages = set()
    for a in soup.find_all("a", href=link_pattern):
        pages.add(int(link_pattern.search(a["href"]).group(1)))
    log(f"chapter links visible in the HTML: {len(pages)}")
    if pages:
        log(f"first page: {min(pages)}   last page: {max(pages)}")
    log("(if this is far below 669, the index loads in parts "
        "and we will handle that later)")
    log()


# ---------------------------------------------------------------- step 4
def check_turath():
    log("=== 4. turath.io shortcut (experimental) ===")
    attempts = [
        ("book info", f"{TURATH_API}/book",
         {"id": BOOK_ID, "include": "indexes", "ver": 3}),
        ("search by title", f"{TURATH_API}/search",
         {"q": "الفقه على المذاهب الأربعة", "ver": 3}),
    ]
    for name, url, params in attempts:
        try:
            response, elapsed = fetch(url, params=params)
            log(f"{name}: status {response.status_code}   time {elapsed:.2f}s")
            if response.ok:
                data = response.json()
                safe_name = name.replace(" ", "_")
                (OUTPUT_DIR / f"turath_{safe_name}.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                if isinstance(data, dict):
                    log(f"  top-level keys: {list(data.keys())[:15]}")
        except (requests.RequestException, ValueError) as error:
            log(f"{name}: failed -> {error}")
        time.sleep(DELAY_SECONDS)

    # Full book file: only ask for its size (HEAD), do not download it yet.
    url = f"{TURATH_FILES}/books-v3/{BOOK_ID}.json"
    try:
        response, elapsed = fetch(url, method="HEAD")
        size = response.headers.get("Content-Length")
        size_text = f"{int(size) / 1024 / 1024:.1f} MB" if size else "unknown"
        log(f"full book file: status {response.status_code}   size {size_text}")
    except requests.RequestException as error:
        log(f"full book file: failed -> {error}")
    log()


# ---------------------------------------------------------------- summary
def summarize(samples):
    log("=== 5. estimate for the whole book ===")
    if not samples:
        log("no page samples were collected")
        return
    count = len(samples)
    avg = {key: sum(s[key] for s in samples) / count
           for key in ("raw", "compressed", "text", "seconds")}
    pages = TOTAL_PAGES_ESTIMATE
    log(f"average request time: {avg['seconds']:.2f}s")
    log(f"raw HTML total:        {avg['raw'] * pages / 1024 / 1024:.0f} MB")
    log(f"compressed HTML total: {avg['compressed'] * pages / 1024 / 1024:.0f} MB")
    log(f"text total (upper):    {avg['text'] * pages / 1024 / 1024:.0f} MB")
    for delay in (1.5, 1.0, 0.5):
        minutes = (avg["seconds"] + delay) * pages / 60
        log(f"download time with {delay}s delay: about {minutes:.0f} minutes")


# ---------------------------------------------------------------- main
def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUTPUT_DIR.mkdir(exist_ok=True)
    samples = []

    steps = [check_robots, inspect_index]
    for step in steps:
        try:
            step()
        except requests.RequestException as error:
            log(f"{step.__name__} failed -> {error}\n")
        time.sleep(DELAY_SECONDS)

    for page_number, label in SAMPLE_PAGES.items():
        try:
            samples.append(inspect_page(page_number, label))
        except requests.RequestException as error:
            log(f"page {page_number} failed -> {error}\n")
        time.sleep(DELAY_SECONDS)

    check_turath()
    summarize(samples)

    (OUTPUT_DIR / "report.txt").write_text("\n".join(report_lines),
                                           encoding="utf-8")
    print(f"\nDone. Send me the files inside: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
