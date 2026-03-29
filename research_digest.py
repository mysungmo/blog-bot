"""
research_digest.py
매주 화·목·토 오전 7시 KST 실행
PubMed 최신 논문 5편 + 건강 뉴스 RSS 기사 → Claude 한국어 요약 → Unsplash 이미지 → 이메일 발송
"""

import os
import random
import smtplib
import time as time_module
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import anthropic
import feedparser
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TO_EMAIL = os.environ["TO_EMAIL"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]

MODEL = "claude-sonnet-4-20250514"

# PubMed E-utilities 검색 키워드
PUBMED_QUERIES = [
    "ophthalmology[tiab] AND (treatment OR therapy)[tiab]",
    "cataract surgery outcomes",
    "glaucoma diagnosis management",
    "retina disease macular degeneration",
    "dry eye syndrome treatment",
]

# 건강 뉴스 RSS 피드
NEWS_FEEDS = [
    {
        "name": "NYT Health",
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
    },
    {
        "name": "Scientific American",
        "url": "https://www.scientificamerican.com/rss/",
    },
    {
        "name": "TIME Health",
        "url": "https://time.com/feed/",
    },
    {
        "name": "Medical News Today",
        "url": "https://www.medicalnewstoday.com/rss",
    },
]

UNSPLASH_QUERY = "eye ophthalmology vision medical research"

SYSTEM_PROMPT = (
    "당신은 의학 논문과 해외 건강 기사를 한국 독자를 위해 쉽고 명확하게 번역·요약하는 전문가입니다. "
    "전문 용어는 한국어로 표기하고 괄호 안에 영문을 병기합니다. "
    "독자가 핵심 내용을 빠르게 파악할 수 있도록 간결하게 작성합니다."
)


# ── PubMed E-utilities API ────────────────────────────────────────────────────────

def search_pubmed(query: str, max_results: int = 3) -> list[str]:
    """PubMed에서 논문 ID 목록 반환."""
    try:
        resp = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "sort": "pub+date",
                "retmode": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"    PubMed 검색 오류: {e}")
        return []


def fetch_pubmed_details(pmid: str) -> dict:
    """PubMed ID로 논문 제목·초록·저자 정보 반환."""
    try:
        resp = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "xml"},
            timeout=10,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        article = root.find(".//Article")
        if article is None:
            return {}

        title_el = article.find("ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_texts = article.findall(".//AbstractText")
        abstract = " ".join("".join(el.itertext()) for el in abstract_texts)[:800]

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else "PubMed"

        return {
            "title": title.strip(),
            "abstract": abstract.strip(),
            "source": journal,
            "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "type": "paper",
        }
    except Exception as e:
        print(f"    PubMed 상세 오류 (PMID {pmid}): {e}")
        return {}


def fetch_pubmed_papers(n: int = 5) -> list[dict]:
    """다양한 키워드로 논문 n편 수집."""
    papers = []
    queries = random.sample(PUBMED_QUERIES, min(n, len(PUBMED_QUERIES)))

    for query in queries:
        if len(papers) >= n:
            break
        pmids = search_pubmed(query, max_results=2)
        for pmid in pmids:
            if len(papers) >= n:
                break
            detail = fetch_pubmed_details(pmid)
            if detail and detail.get("title"):
                papers.append(detail)
            time_module.sleep(0.4)  # NCBI API 속도 제한 준수

    return papers


# ── RSS 뉴스 기사 검색 ────────────────────────────────────────────────────────────

def fetch_news_articles(n: int = 3) -> list[dict]:
    """RSS 피드에서 건강 뉴스 기사 n편 수집."""
    articles = []
    feeds = random.sample(NEWS_FEEDS, len(NEWS_FEEDS))

    for feed_info in feeds:
        if len(articles) >= n:
            break
        try:
            feed = feedparser.parse(feed_info["url"])
            entries = [e for e in feed.entries if e.get("title") and e.get("link")]
            if not entries:
                continue
            entry = random.choice(entries[:8])
            summary = entry.get("summary", entry.get("description", ""))
            summary = re.sub(r"<[^>]+>", " ", summary).strip()[:600]
            articles.append({
                "title": entry.title,
                "abstract": summary,
                "source": feed_info["name"],
                "link": entry.link,
                "type": "news",
            })
        except Exception as e:
            print(f"    RSS 오류 ({feed_info['name']}): {e}")

    return articles


# ── Unsplash 이미지 ───────────────────────────────────────────────────────────────

def fetch_unsplash_image(query: str) -> dict:
    """Unsplash에서 이미지 URL + 작가 정보 반환."""
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 10, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            photo = random.choice(results[:5])
            return {
                "url": photo["urls"]["regular"],
                "author": photo["user"]["name"],
                "author_link": photo["user"]["links"]["html"],
            }
    except Exception as e:
        print(f"    Unsplash 오류: {e}")
    return {}


# ── Claude 한국어 요약 생성 ───────────────────────────────────────────────────────

def summarize_item(client: anthropic.Anthropic, item: dict) -> str:
    """논문 또는 기사를 한국어 블로그 카드용으로 요약."""
    item_type = "논문" if item["type"] == "paper" else "기사"
    content_label = "초록" if item["type"] == "paper" else "내용"

    message = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"다음 해외 안과 {item_type}을 한국어로 요약해주세요.\n\n"
                    f"제목: {item['title']}\n"
                    f"출처: {item['source']}\n"
                    f"{content_label}: {item.get('abstract', '')}\n\n"
                    "요약 형식:\n"
                    "• 핵심 내용을 3~5문장으로 간결하게 정리\n"
                    "• 임상적 의의나 독자에게 도움이 되는 시사점 1문장 추가\n"
                    "• 전문 용어는 한국어(영문) 병기"
                ),
            }
        ],
    )
    return message.content[0].text.strip()


def build_digest(client: anthropic.Anthropic, papers: list[dict], news: list[dict]) -> list[dict]:
    """모든 항목에 한국어 요약 추가."""
    results = []
    all_items = papers + news
    for item in all_items:
        print(f"    요약 중: {item['title'][:50]}...")
        summary_ko = summarize_item(client, item)
        results.append({**item, "summary_ko": summary_ko})
    return results


# ── 이메일 HTML 구성 ──────────────────────────────────────────────────────────────

def build_email_html(items: list[dict], image: dict, generated_at: str) -> str:
    # 이미지 블록
    image_block = ""
    if image.get("url"):
        image_block = f"""
        <div style="margin-bottom:32px; border-radius:10px; overflow:hidden;
                    box-shadow:0 4px 12px rgba(0,0,0,0.12);">
            <img src="{image['url']}" alt="Eye Research"
                 style="width:100%; display:block; max-height:300px; object-fit:cover;">
            <p style="margin:0; padding:6px 12px; background:#1a1a2e;
                      font-size:11px; color:#aaa; text-align:right;">
                Photo by
                <a href="{image.get('author_link','#')}" target="_blank"
                   style="color:#7eb8f7;">{image.get('author','')}</a>
                on Unsplash
            </p>
        </div>
        """

    # 항목 카드 구성
    paper_cards = ""
    news_cards = ""

    for item in items:
        badge_color = "#2e7d32" if item["type"] == "paper" else "#1565c0"
        badge_text = "논문" if item["type"] == "paper" else "뉴스"

        card = f"""
        <div style="margin-bottom:24px; padding:20px; background:#fff;
                    border-radius:8px; box-shadow:0 2px 6px rgba(0,0,0,0.07);">
            <div style="margin-bottom:10px;">
                <span style="display:inline-block; padding:2px 10px; border-radius:12px;
                             background:{badge_color}; color:#fff; font-size:11px;
                             font-weight:600;">{badge_text}</span>
                <span style="margin-left:8px; font-size:12px; color:#888;">{item['source']}</span>
            </div>
            <h3 style="margin:0 0 10px; font-size:16px; color:#1a1a2e; line-height:1.5;">
                {item['title']}
            </h3>
            <p style="margin:0 0 14px; line-height:1.8; color:#444; font-size:14px;">
                {item['summary_ko'].replace(chr(10), '<br>')}
            </p>
            <a href="{item['link']}" target="_blank"
               style="display:inline-block; padding:6px 16px; background:#4A90D9;
                      color:#fff; border-radius:4px; text-decoration:none;
                      font-size:13px; font-weight:600;">
               원문 보기 →
            </a>
        </div>
        """

        if item["type"] == "paper":
            paper_cards += card
        else:
            news_cards += card

    section = lambda title, icon, cards: f"""
        <h2 style="margin:32px 0 16px; font-size:17px; color:#1a1a2e;
                   border-bottom:2px solid #4A90D9; padding-bottom:8px;">
            {icon} {title}
        </h2>
        {cards}
    """ if cards else ""

    return f"""
    <html><body style="font-family:'Apple SD Gothic Neo',Arial,sans-serif;
                       background:#f0f4f8; padding:32px; margin:0;">
        <div style="max-width:680px; margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1a1a2e,#4A90D9);
                        padding:28px 32px; border-radius:10px 10px 0 0; color:#fff;">
                <h1 style="margin:0; font-size:22px;">안과 연구 다이제스트</h1>
                <p style="margin:6px 0 0; font-size:13px; opacity:0.85;">
                    PubMed 최신 논문 + 해외 건강 뉴스 | {generated_at}
                </p>
            </div>
            <div style="padding:24px 16px;">
                {image_block}
                {section('최신 안과 논문', '🔬', paper_cards)}
                {section('해외 건강 뉴스', '📰', news_cards)}
            </div>
            <p style="text-align:center; font-size:12px; color:#aaa; margin-top:8px;">
                이 메일은 Claude AI가 PubMed 및 해외 뉴스 RSS를 기반으로 자동 생성한 콘텐츠입니다.
            </p>
        </div>
    </body></html>
    """


# ── 이메일 발송 ───────────────────────────────────────────────────────────────────

def send_email(items: list[dict], image: dict, generated_at: str) -> None:
    html_body = build_email_html(items, image, generated_at)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[안과 리서치 다이제스트] 논문·뉴스 {len(items)}편 — {generated_at}"
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{generated_at}] 리서치 다이제스트 생성 시작")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print("PubMed 논문 검색 중 (5편)...")
    papers = fetch_pubmed_papers(n=5)
    print(f"  → {len(papers)}편 수집 완료")

    print("RSS 뉴스 기사 검색 중 (3편)...")
    news = fetch_news_articles(n=3)
    print(f"  → {len(news)}편 수집 완료")

    print("Unsplash 이미지 검색 중...")
    image = fetch_unsplash_image(UNSPLASH_QUERY)

    print("Claude 한국어 요약 생성 중...")
    items = build_digest(client, papers, news)

    print("이메일 발송 중...")
    send_email(items, image, generated_at)

    print(f"완료: {TO_EMAIL} 으로 발송되었습니다. (총 {len(items)}편)")


if __name__ == "__main__":
    main()
