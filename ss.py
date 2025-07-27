import sys
import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import hashlib
from PIL import Image
import imagehash
import io
import spacy
import subprocess
import json

nlp = spacy.load("en_core_web_sm")

search_engines = {
    "DuckDuckGo": "https://html.duckduckgo.com/html/?q=",
    "GitHub": "https://github.com/search?q=",
    "Bing": "https://www.bing.com/search?q=",
    "Yahoo": "https://search.yahoo.com/search?p=",
    "Scholar": "https://scholar.google.com/scholar?q=",
    "ResearchGate": "https://www.researchgate.net/search?q=",
    "Reddit": "https://www.reddit.com/search/?q=",
    "LinkedIn": "https://www.bing.com/search?q=site%3Alinkedin.com+",
}

trusted_domains = [
    "github.com", "linkedin.com", "researchgate.net", "scholar.google.com",
    "ctu.edu.vn", "edu.vn", "ac.uk", "edu", "org"
]

def is_trusted(url, keyword):
    domain = urlparse(url).netloc.lower()
    score = 0
    for trusted in trusted_domains:
        if trusted in domain:
            score += 2
    if keyword.lower().replace(" ", "") in url.lower().replace(" ", ""):
        score += 2
    if domain.startswith("www."):
        domain = domain[4:]
    if keyword.split()[0].lower() in domain:
        score += 1
    return score

email_regex = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
phone_regex = re.compile(r"(\+?\d[\d\s.-]{7,}\d)")

avatar_hashes = {}

async def fetch_page(session, url):
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            return await resp.text()
    except:
        return ""

async def fetch_bytes(session, url):
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            return await resp.read()
    except:
        return b""

async def search(engine, query):
    url = search_engines[engine] + query.replace(" ", "+")
    async with aiohttp.ClientSession() as session:
        html = await fetch_page(session, url)
        soup = BeautifulSoup(html, "html.parser")

        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and not any(x in href for x in ["javascript", "mailto"]):
                links.add(href)
        return engine, list(links)

async def extract_info(session, url):
    content = await fetch_page(session, url)
    emails = email_regex.findall(content)
    phones = phone_regex.findall(content)

    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(" ", strip=True)
    desc = text[:300]
    doc = nlp(desc)
    labels = set(ent.label_ for ent in doc.ents)

    # Avatar detection
    avatar_found = None
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and any(word in src.lower() for word in ["avatar", "profile", "userpic"]):
            if src.startswith("/"):
                src = urlparse(url)._replace(path=src).geturl()
            elif not src.startswith("http"):
                continue
            data = await fetch_bytes(session, src)
            try:
                image = Image.open(io.BytesIO(data))
                hash_ = imagehash.phash(image)
                for h in avatar_hashes:
                    if abs(h - hash_) <= 4:
                        avatar_found = f"Trùng với avatar trên {avatar_hashes[h]}"
                avatar_hashes[hash_] = url
            except:
                continue
            break

    return set(emails), set(phones), desc[:200], avatar_found

# -------------------------------
# 🛰️ MODULE: WHOIS + IP LOOKUP + WAYBACK + SHODAN SCRAPE
# -------------------------------

def run_whois(domain):
    try:
        result = subprocess.run(["whois", domain], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return result.stdout.strip().split('\n')[:10]  # Chỉ 10 dòng đầu
    except:
        return []

def ip_lookup(ip):
    try:
        url = f"http://ip-api.com/json/{ip}"
        resp = requests.get(url, timeout=5).json()
        return f"{resp.get('country', '')}, {resp.get('org', '')}, {resp.get('as', '')}"
    except:
        return "Không tra được IP"

async def wayback_check(session, domain):
    try:
        url = f"https://web.archive.org/cdx/search/cdx?url={domain}&output=json&fl=timestamp,original&collapse=urlkey"
        raw = await fetch_page(session, url)
        if raw:
            data = json.loads(raw)
            if len(data) > 1:
                first = data[1][0][:4]
                last = data[-1][0][:4]
                return f"Snapshot đầu: {first}, cuối: {last}"
    except:
        pass
    return "Không có dữ liệu Wayback"

async def shodan_scrape(session, query):
    try:
        url = f"https://www.shodan.io/search?query={query.replace(' ', '+')}"
        html = await fetch_page(session, url)
        soup = BeautifulSoup(html, "html.parser")
        ips = [el.text.strip() for el in soup.select(".ip")]
        return ips[:3]
    except:
        return []

# -------------------------------

async def gather_all(query):
    tasks = [search(engine, query) for engine in search_engines]
    results = await asyncio.gather(*tasks)
    return results

async def main(query):
    all_links = set()
    link_meta = []

    print(f"\n[🔍] OSINT cho: \"{query}\"\n")

    results = await gather_all(query)
    for engine, links in results:
        for link in links:
            all_links.add((engine, link))

    session = aiohttp.ClientSession()
    enriched = []

    for engine, link in sorted(all_links):
        emails, phones, desc, avatar_note = await extract_info(session, link)
        score = is_trusted(link, query)
        enriched.append((score, engine, link, emails, phones, desc, avatar_note))

    await session.close()
    enriched.sort(reverse=True, key=lambda x: x[0])
    top = enriched[0] if enriched else None

    for score, engine, link, emails, phones, desc, avatar_note in enriched:
        print(f"[{engine}] {link}")
        if emails:
            print("    ✉️  Email:", ", ".join(emails))
        if phones:
            print("    📱 Phone:", ", ".join(phones))
        if desc:
            print("    🧠 Desc:", desc[:150], "...")
        if avatar_note:
            print("    🖼 Avatar:", avatar_note)
        print()

    if top:
        print(f"[💡] Alias đáng tin nhất:")
        print(f"     → [{top[1]}] {top[2]}")
        if top[3]:
            print(f"     ✉️  {', '.join(top[3])}")
        if top[4]:
            print(f"     📱 {', '.join(top[4])}")

    print(f"\n[+] Tổng link tìm được: {len(enriched)}")

    # WHOIS & Wayback & Shodan scrape demo
    domain = urlparse(top[2]).netloc if top else ""
    print(f"\n[🔍 WHOIS cho {domain}]")
    for line in run_whois(domain):
        print("    ", line)

    print(f"\n[🕓 Wayback check]")
    print("    ", await wayback_check(session, domain))

    print(f"\n[🛰️ Shodan IP scrape]")
    for ip in await shodan_scrape(session, query):
        print("    IP:", ip)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python osint_advanced_tool.py \"Tên hoặc Alias\"")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
