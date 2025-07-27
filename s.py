import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import defaultdict

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

def detect_platform(link):
    if "github.com" in link: return "GitHub"
    if "linkedin.com" in link: return "LinkedIn"
    if "scholar.google.com" in link: return "Google Scholar"
    if "researchgate.net" in link: return "ResearchGate"
    if "reddit.com" in link: return "Reddit"
    if "bing.com" in link: return "Bing"
    if "duckduckgo.com" in link: return "DuckDuckGo"
    if "yahoo.com" in link: return "Yahoo"
    return "Other"

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def group_aliases(links, threshold=0.85):
    groups = []
    visited = set()

    for i, link in enumerate(links):
        if link in visited:
            continue
        group = [link]
        visited.add(link)
        for j in range(i+1, len(links)):
            other = links[j]
            if other in visited:
                continue
            if similarity(link, other) >= threshold:
                group.append(other)
                visited.add(other)
        if len(group) >= 2:  # CHỈ NHÓM ≥2
            groups.append(group)
    return groups

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

        results = []
        for a in soup.find_all("a", href=True):
            href = a.get("href")
            if href.startswith("http") and not any(x in href for x in ["javascript", "mailto"]):
                results.append(href)
        return results

async def gather_links(query):
    tasks = [search(engine, query) for engine in search_engines]
    results = await asyncio.gather(*tasks)
    links = set()
    for result in results:
        for link in result:
            links.add(link)
    return list(links)

def analyze_links(links):
    groups = group_aliases(links)
    grouped_data = []
    for group in groups:
        sim_scores = [round(similarity(group[0], x), 2) for x in group[1:]]
        platforms = [detect_platform(x) for x in group]
        grouped_data.append({
            "aliases": group,
            "similarity_scores": sim_scores,
            "platforms": platforms
        })
    return grouped_data

def display_console(entity_name, grouped_data):
    print(f"\n[🔎] OSINT Analysis Result for: \"{entity_name}\"\n")
    if not grouped_data:
        print("Không phát hiện nhóm alias nào có độ tương đồng cao.")
        return

    for idx, group in enumerate(grouped_data):
        plat_count = defaultdict(int)
        for plat in group["platforms"]:
            plat_count[plat] += 1

        print(f"== Group {idx+1} ({len(group['aliases'])} links) ==")
        for link in group["aliases"]:
            plat = detect_platform(link)
            print(f"  [{plat:14}] {link}")
        if group["similarity_scores"]:
            avg_score = sum(group["similarity_scores"]) / len(group["similarity_scores"])
            print(f"  → Similarity scores: {group['similarity_scores']} (avg: {round(avg_score, 2)})")
        print(f"  → Nền tảng phân bố: " + ", ".join([f"{k}: {v}" for k, v in plat_count.items()]))
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python osint_advanced_console.py \"Full Name\"")
        sys.exit(1)

    query = sys.argv[1]
    links = asyncio.run(gather_links(query))
    grouped_data = analyze_links(links)
    display_console(query, grouped_data)
