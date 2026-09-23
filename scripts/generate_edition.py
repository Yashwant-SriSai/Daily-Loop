import feedparser
from pathlib import Path
import urllib.parse
from datetime import date
import os
import json
import time
import xml.etree.ElementTree as ET
import requests

from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
load_dotenv()

FEEDS = {
    "SOFTWARE DEV": ["https://news.ycombinator.com/rss"],
    "AI": [
        "https://huggingface.co/blog/feed.xml",
        "https://openai.com/news/rss.xml",
    ],
    "ANIME & MANGA": ["https://www.animenewsnetwork.com/all/rss.xml"],
    "TRADING": ["https://feeds.marketwatch.com/marketwatch/topstories/"],
}

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)
MODEL = "openai/gpt-oss-20b"


# ---------------------------------------------------------------------------
# Shared model-calling helper — every function routes through this, so
# rate-limit handling and token-limit debugging only live in one place.
# ---------------------------------------------------------------------------
def call_model(messages, max_retries=5, max_tokens=None):
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_completion_tokens=max_tokens,
            )
            choice = resp.choices[0]
            text = choice.message.content.strip() if choice.message.content else ""

            if choice.finish_reason == "length":
                print(f"  [debug] response was CUT OFF (finish_reason=length, max_tokens={max_tokens})")

            return text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        except RateLimitError:
            wait = 3 * attempt
            print(f"  [rate limit] waiting {wait}s before retry {attempt}/{max_retries}...")
            time.sleep(wait)
    raise RuntimeError("Rate limit persisted after all retries")

# ---------------------------------------------------------------------------
# RSS fetching
# ---------------------------------------------------------------------------
def fetch_headlines(urls, limit=5):
    items = []
    for url in urls:
        parsed = feedparser.parse(url)
        print(f"   [debug] {url} -> status={parsed.get('status')} entries={len(parsed.entries)} bozo={parsed.bozo}")
        for entry in parsed.entries[:limit]:
            items.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:400],
                "link": entry.get("link", ""),
            })
    return items



def fetch_recent_papers(query="artificial intelligence", limit=5):
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": limit,
    })
    url = f"https://export.arxiv.org/api/query?{params}"

    resp = requests.get(url, headers={"User-Agent": "daily-loop-digest/1.0"})
    print(f"   [debug] arXiv -> status={resp.status_code}")

    if resp.status_code != 200:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    entries = root.findall("atom:entry", ns)

    papers = []
    for entry in entries:
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")[:600]
        link = entry.find("atom:link[@type='text/html']", ns)
        link_href = link.attrib["href"] if link is not None else entry.find("atom:id", ns).text
        authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)[:3]]

        papers.append({
            "title": title,
            "authors": ", ".join(authors),
            "summary": summary,
            "link": link_href,
        })
    return papers


# ---------------------------------------------------------------------------
# News synthesis
# ---------------------------------------------------------------------------
def synthesize_topic(topic, headlines):
    if not headlines:
        return None

    source_text = "\n\n".join(f"- {h['title']}: {h['summary']}" for h in headlines)

    text = call_model(
        [
            {
                "role": "system",
                "content": (
                    "You are a wire-service news editor. Given several raw headlines "
                    "and snippets on one topic, write ONE reconciled brief in your own "
                    "words. Never invent facts not present in the source material. "
                    'Respond ONLY with JSON: {"headline": "...", "body": "4-5 sentences"}'
                ),
            },
            {"role": "user", "content": f"Topic: {topic}\n\nSources:\n{source_text}"},
        ],
        max_tokens=800,
    )

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [warn] could not parse model output for {topic}: {text[:200]}")
        return None


def write_lead_story(topic, brief):
    text = call_model(
        [
            {
                "role": "system",
                "content": (
                    "You are a news feature writer. Expand the given brief into "
                    "exactly 3 paragraphs for a daily digest. Stay strictly grounded "
                    "in the brief — do not introduce new facts. Plain, direct prose. "
                    'Respond ONLY with JSON: {"paragraphs": ["p1", "p2", "p3"]}'
                ),
            },
            {
                "role": "user",
                "content": f"Topic: {topic}\nHeadline: {brief['headline']}\nBrief: {brief['body']}",
            },
        ],
        max_tokens=1000,
    )
    try:
        return json.loads(text)["paragraphs"]
    except (json.JSONDecodeError, KeyError):
        return [brief["body"]]


def write_eli5():
    text = call_model(
        [
            {
                "role": "system",
                "content": (
                    "Pick one interesting, non-obvious technical concept related to "
                    "AI, software, boxing, trading, or anime/manga. Explain it as a "
                    "simple analogy a 5-year-old could follow. "
                    'Respond ONLY with JSON: {"title": "a short question", "explanation": "the analogy, 2-3 sentences"}'
                ),
            },
            {"role": "user", "content": "Generate today's topic."},
        ],
        max_tokens=1200,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [warn] could not parse ELI5 output: {text[:200]}")
        return {"title": "N/A", "explanation": "Could not generate today's ELI5 topic."}


def write_paper_summary(paper):
    text = call_model(
        [
            {
                "role": "system",
                "content": (
                    "Summarize this research paper abstract in plain language, "
                    "2-3 sentences, for a non-expert reader. Stay strictly grounded "
                    "in the abstract given — do not invent findings. "
                    'Respond ONLY with JSON: {"plain_summary": "..."}'
                ),
            },
            {"role": "user", "content": f"Title: {paper['title']}\n\nAbstract: {paper['summary']}"},
        ],
        max_tokens=500,
    )
    try:
        return json.loads(text)["plain_summary"]
    except (json.JSONDecodeError, KeyError):
        return paper["summary"][:300]


# ---------------------------------------------------------------------------
# DSA generation + verification
# ---------------------------------------------------------------------------
def generate_dsa(difficulty="basic"):
    level = "an Easy or Medium" if difficulty == "basic" else "a Hard-level"
    system = (
        f"You are a LeetCode-style problem setter. Create {level} coding problem. "
        "Provide a complete, correct Python solution as a single function — keep the "
        "code compact, no comments, no docstring. Provide exactly 2 test cases as "
        "literal Python values (not strings of code). Keep the explanation to 1-2 "
        "short sentences. "
        'Respond ONLY with JSON, no other text: {'
        '"title": "...", "difficulty": "Easy|Medium|Hard", '
        '"prompt": "problem description, 1-2 sentences", '
        '"function_name": "the function name used in solution", '
        '"python_solution": "full function code as a string, def included", '
        '"explanation": "1-2 sentences on the approach", '
        '"test_cases": [{"args": [<arg1>, <arg2>], "expected": <output>}]'
        '}'
    )
    text = call_model(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "Generate one."},
        ],
        max_tokens=8000,
    )

    if not text:
        print("  [warn] model returned empty response")
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [warn] could not parse DSA output: {text[:200]}")
        return None

def verify_dsa(problem):
    if problem is None:
        return False

    namespace = {}
    try:
        exec(problem["python_solution"], namespace)
        func = namespace[problem["function_name"]]
    except Exception as e:
        print(f"  [warn] solution code failed to load: {e}")
        return False

    for case in problem["test_cases"]:
        try:
            result = func(*case["args"])
        except Exception as e:
            print(f"  [warn] solution raised an error on {case['args']}: {e}")
            return False
        if result != case["expected"]:
            print(f"  [warn] wrong output for {case['args']}: got {result}, expected {case['expected']}")
            return False
    return True


def get_verified_dsa(difficulty="basic", max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        print(f"  Generating DSA problem (attempt {attempt}, difficulty={difficulty})...")
        problem = generate_dsa(difficulty)
        if verify_dsa(problem):
            print(f"  -> verified: {problem['title']} ({problem['difficulty']})")
            return problem
        print("  -> failed verification, retrying...")
        time.sleep(2)
    raise RuntimeError(f"Could not generate a verified {difficulty} DSA problem after {max_attempts} attempts")


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    all_briefs = {}
    topic_headline_counts = {}

    for topic, urls in FEEDS.items():
        headlines = fetch_headlines(urls)
        topic_headline_counts[topic] = len(headlines)
        print(f"\nFetched {len(headlines)} headlines for {topic}")

        brief = synthesize_topic(topic, headlines)
        if brief:
            all_briefs[topic] = brief
            print(f"  -> {brief['headline']}")
        else:
            print(f"  -> skipped (no usable brief)")

    lead_topic = max(all_briefs, key=lambda t: topic_headline_counts[t])
    print(f"\nLead topic chosen: {lead_topic}")
    paragraphs = write_lead_story(lead_topic, all_briefs[lead_topic])

    print("\nGenerating ELI5...")
    eli5 = write_eli5()

    print("\nGenerating DSA problems...")
    dsa_basic = get_verified_dsa(difficulty="basic")
    dsa_advanced = get_verified_dsa(difficulty="advanced",max_attempts=5)

    print("\nFetching research papers...")
    papers = fetch_recent_papers()
    paper = papers[0] if papers else None
    paper_summary = write_paper_summary(paper) if paper else None

    briefs_list = [
        {
            "category": topic,
            "source_count": topic_headline_counts[topic],
            "headline": b["headline"],
            "body": b["body"],
        }
        for topic, b in all_briefs.items()
        if topic != lead_topic
    ]

    edition = {
        "generated_date": str(date.today()),

        "lead": {
            "topic": lead_topic,
            "headline": all_briefs[lead_topic]["headline"],
            "source_count": topic_headline_counts[lead_topic],
            "paragraphs": paragraphs,
        },
        "briefs": briefs_list,
        "explainli5": eli5,
        "dsa": {
            "basic": dsa_basic,
            "advanced": dsa_advanced,
        },
        "paper": {
            "title": paper["title"],
            "authors": paper["authors"],
            "summary": paper_summary,
            "link": paper["link"],
        } if paper else None,
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "edition.json"
    out_path.write_text(json.dumps(edition, indent=2))
    print(f"\nWrote {out_path}")