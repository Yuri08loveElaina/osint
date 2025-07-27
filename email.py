import sys
import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse

search_engines = {
    "DuckDuckGo": "https://html.duckduckgo.com/html/?q=",
    "GitHub": "https://github.com/search?q=",
    "Bing": "https://www.bing.com/search?q=",
    "Yahoo": "https://search.yahoo.com/search?p=",
    "GoogleScholar": "https://scholar.google.com/scholar?q=",
    "ResearchGate": "https://www.researchgate.net/search?q=",
    "Reddit": "https://www.reddit.com/search/?q=",
    "LinkedIn": "https://www.bing.com/search?q=site%3Alinkedin.com+",
}

# Ưu tiên domain đáng tin
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

async def fetch_page(session, url):
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            return await resp.text()
    except:
        return ""

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

async def extract_emails_and_phones(session, url):
    content = await fetch_page(session, url)
    emails = email_regex.findall(content)
    phones = phone_regex.findall(content)
    return set(emails), set(phones)

async def gather_all(query):
    tasks = [search(engine, query) for engine in search_engines]
    results = await asyncio.gather(*tasks)
    return results

async def main(query):
    all_links = set()
    link_meta = []

    print(f"\n[🔍] Bắt đầu tìm kiếm OSINT cho: \"{query}\"\n")

    results = await gather_all(query)

    for engine, links in results:
        for link in links:
            all_links.add((engine, link))

    session = aiohttp.ClientSession()
    enriched = []

    for engine, link in sorted(all_links):
        emails, phones = await extract_emails_and_phones(session, link)
        score = is_trusted(link, query)
        enriched.append((score, engine, link, emails, phones))

    await session.close()

    # Sắp xếp theo độ tin cậy
    enriched.sort(reverse=True, key=lambda x: x[0])
    top = enriched[0] if enriched else None

    for score, engine, link, emails, phones in enriched:
        print(f"[{engine}] {link}")
        if emails:
            print("    ✉️ Email: " + ", ".join(emails))
        if phones:
            print("    📱 Phone: " + ", ".join(phones))
        print()

    if top:
        print(f"[💡] Alias đáng tin cậy nhất:")
        print(f"     → [{top[1]}] {top[2]}")
        if top[3]:
            print(f"     ✉️ {', '.join(top[3])}")
        if top[4]:
            print(f"     📱 {', '.join(top[4])}")

    print(f"\n[+] Tổng số link thu thập được: {len(enriched)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python osint_extract_info.py \"Tên hoặc Alias\"")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
