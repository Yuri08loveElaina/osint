import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup

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

async def fetch(session, url):
    try:
        async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as resp:
            return await resp.text()
    except:
        return ""

async def search(engine, query):
    url = search_engines[engine] + query.replace(' ', '+')
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url)
        soup = BeautifulSoup(html, 'html.parser')

        links = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if href.startswith("http") and not any(x in href for x in ["javascript", "mailto"]):
                links.add(href)
        return engine, list(links)

async def gather_all(query):
    tasks = [search(engine, query) for engine in search_engines]
    results = await asyncio.gather(*tasks)
    return results

def print_links(results):
    total = 0
    for engine, links in results:
        for link in links:
            print(f"[{engine}] {link}")
            total += 1
    print(f"\n[+] Tổng số link thu thập được: {total}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python osint_plain_console.py \"Từ khóa cần tìm\"")
        sys.exit(1)

    query = sys.argv[1]
    results = asyncio.run(gather_all(query))
    print_links(results)
