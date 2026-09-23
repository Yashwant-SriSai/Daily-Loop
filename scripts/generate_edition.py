import feedparser
from pathlib import Path
import urllib.parse
from datetime import date
import os
import json
import time
import xml.etree.ElementTree as ET
import requests

from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import load_dotenv
load_dotenv()
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FEEDS = {
    "SOFTWARE DEV": ["https://news.ycombinator.com/rss"],
    "AI": [
        "https://huggingface.co/blog/feed.xml",
        "https://openai.com/news/rss.xml",
    ],
    "ANIME & MANGA": ["https://www.animenewsnetwork.com/all/rss.xml"],
    "TRADING": ["https://feeds.marketwatch.com/marketwatch/topstories/"],
    "TRENDING TECH": ["https://dev.to/feed/tag/programming"],
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
        except RateLimitError as e:
                msg = str(e)
                if "tokens per day" in msg or "TPD" in msg:
                    print(f"  [rate limit] DAILY token limit hit — retrying won't help today.")
                    print(f"  {msg}")
                    raise RuntimeError("Daily token limit reached. Try again after it resets.")
                print(f"  [rate limit] {e}")
                wait = 15 * attempt
                print(f"  [rate limit] waiting {wait}s before retry {attempt}/{max_retries}...")
                time.sleep(wait)
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
                    "and snippets on one topic, write a full, substantial summary — "
                    "NOT a headline, NOT a one-liner. Write a proper news summary of "
                    "8-10full sentences that explains what actually happened, why it "
                    "matters, and any relevant context, as if briefing someone who "
                    "hasn't seen any of the source material. Never invent facts not "
                    "present in the source material. "
                    'Respond ONLY with JSON: {"headline": "a short headline, under 12 words", "body": "the 8-10 sentence summary"}'
                ),
            },
            {"role": "user", "content": f"Topic: {topic}\n\nSources:\n{source_text}"},
        ],
        max_tokens=2000,
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
                    "AI, software, boxing, trading, or anime/manga. Explain it in TWO "
                    "parts, both substantial — not vague, not just a one-line analogy:\n\n"
                    "1. A simple analogy a 5-year-old could follow, 2-3 sentences, "
                    "concrete and vivid.\n"
                    "2. A real, deeper explanation for an adult reader — 5-7 sentences "
                    "covering how it actually works, why it matters, and one concrete "
                    "example or real-world application. Use the real technical terms "
                    "here, don't oversimplify this part.\n\n"
                    'Respond ONLY with JSON: {"title": "a short question", "explanation": "part 1, the simple analogy", "deep_dive": "part 2, the real explanation, 5-7 sentences"}'
                ),
            },
            {"role": "user", "content": "Generate today's topic."},
        ],
        max_tokens=2000,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"  [warn] could not parse ELI5 output: {text[:200]}")
        return {"title": "N/A", "explanation": "Could not generate today's ELI5 topic."}

    # Guard against the model omitting a key even when JSON parses fine
    result.setdefault("title", "N/A")
    result.setdefault("explanation", "")
    result.setdefault("deep_dive", "")
    return result
def write_paper_summary(paper):
    text = call_model(
        [
            {
                "role": "system",
                "content": (
                    "Summarize this research paper's abstract in plain language for a "
                    "non-expert reader.\n\n"
                    "STRICT REQUIREMENT: your \"plain_summary\" field must be AT LEAST "
                    "150 words. A short answer is a FAILURE. Write in this structure:\n"
                    "1. What problem does this paper address? (2 sentences)\n"
                    "2. What approach or method does it use? (2 sentences)\n"
                    "3. What is the key finding or result? (2 sentences)\n"
                    "4. Why does this matter, in practical terms? (2 sentences)\n\n"
                    "That is 8 sentences minimum. Stay strictly grounded in the "
                    "abstract given — do not invent findings not stated in it.\n\n"
                    'Respond ONLY with JSON: {"plain_summary": "your full 8+ sentence answer here"}'
                ),
            },
            {"role": "user", "content": f"Title: {paper['title']}\n\nAbstract: {paper['summary']}"},
        ],
        max_tokens=2500,
    )
    try:
        result = json.loads(text)["plain_summary"]
    except (json.JSONDecodeError, KeyError):
        print(f"  [warn] could not parse paper summary: {text[:200]}")
        return paper["summary"][:300]

    word_count = len(result.split())
    if word_count < 100:
        print(f"  [warn] paper summary too short ({word_count} words), retrying once with a stronger nudge")
        text2 = call_model(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a DETAILED plain-language summary of this abstract, "
                        "at least 150 words, covering the problem, method, result, "
                        "and significance. Do not write a short answer. "
                        'Respond ONLY with JSON: {"plain_summary": "..."}'
                    ),
                },
                {"role": "user", "content": f"Title: {paper['title']}\n\nAbstract: {paper['summary']}"},
            ],
            max_tokens=2500,
        )
        try:
            retry_result = json.loads(text2)["plain_summary"]
            if len(retry_result.split()) > word_count:
                return retry_result
        except (json.JSONDecodeError, KeyError):
            pass

    return result

# ---------------------------------------------------------------------------
# DSA generation + verification
# ---------------------------------------------------------------------------
def generate_dsa(difficulty="basic"):
    level = "an Easy or Medium" if difficulty == "basic" else "a Hard-level"
    system = (
         f"You are a LeetCode-style problem setter. Create {level} coding problem. "
        "Provide a complete, correct Python solution as a single function — keep the "
        "code compact, no comments, no docstring. Provide exactly 2 test cases as "
        "literal Python values (not strings of code). "
        "Write a REAL, substantial explanation of the approach — 4-6 sentences "
        "covering the core idea, why it works, and any key insight or trick used. "
        "Do not write a vague one-liner. "
        "Also state the exact time complexity and space complexity, each with a "
        "one-sentence justification of why. "
        'Respond ONLY with JSON, no other text: {'
        '"title": "...", "difficulty": "Easy|Medium|Hard", '
        '"prompt": "problem description, 2-3 sentences", '
        '"function_name": "the function name used in solution", '
        '"python_solution": "full function code as a string, def included", '
        '"explanation": "4-6 sentences on the approach and why it works", '
        '"time_complexity": "e.g. O(n log n) — reason in one sentence", '
        '"space_complexity": "e.g. O(n) — reason in one sentence", '
        '"test_cases": [{"args": [<arg1>, <arg2>], "expected": <output>}]'
        '}'
    )
    text = call_model(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "Generate one."},
        ],
        max_tokens=5000,
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
        time.sleep(3) 
    print("\n--- Synthesis results ---")
    for topic in FEEDS:
          status = "OK" if topic in all_briefs else "SKIPPED"
          print(f"  {topic}: {status}")

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