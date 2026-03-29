import os
import random
import smtplib
import anthropic
import feedparser
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TO_EMAIL = os.environ["TO_EMAIL"]
UNSPLASH_ACCESS_KEY = os.environ["UNSPLASH_ACCESS_KEY"]

MODEL = "claude-sonnet-4-20250514"

# 각 카테고리별 RSS 피드 및 Unsplash 검색어 설정
TOPIC_CONFIGS = [
    {
        "category": "안과 질환 정보",
        "feed_urls": [
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=ophthalmology+eye+disease+treatment&format=abstract&limit=15",
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=glaucoma+cataract+macular+degeneration&format=abstract&limit=15",
        ],
        "unsplash_query": "ophthalmology eye disease medical",
        "prompt_suffix": (
            "위 논문/기사를 바탕으로 안과 질환(원인·증상·치료·예방)을 "
            "일반 독자가 이해하기 쉽게 설명하는 블로그 글을 작성해주세요. "
            "최신 연구 동향을 자연스럽게 녹여주세요."
        ),
    },
    {
        "category": "눈 건강 상식",
        "feed_urls": [
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=eye+health+prevention+lifestyle+vision&format=abstract&limit=15",
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=dry+eye+digital+eye+strain+nutrition&format=abstract&limit=15",
        ],
        "unsplash_query": "eye health vision care lifestyle",
        "prompt_suffix": (
            "위 논문/기사를 참고하여 일상에서 실천할 수 있는 눈 건강 관리법을 "
            "친근하고 실용적으로 설명하는 블로그 글을 작성해주세요."
        ),
    },
    {
        "category": "밀양성모안과 홍보",
        "feed_urls": [
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=cataract+surgery+refractive+LASIK+outcomes&format=abstract&limit=15",
            "https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=retina+glaucoma+clinic+treatment+advances&format=abstract&limit=15",
        ],
        "unsplash_query": "eye clinic ophthalmologist doctor hospital",
        "prompt_suffix": (
            "위 최신 논문/기사를 바탕으로 해당 치료 기술을 소개하면서, "
            "경남 밀양의 밀양성모안과(라식·라섹·백내장·녹내장·망막·소아안과 전문)를 "
            "자연스럽게 홍보하는 블로그 글을 작성해주세요. "
            "지역 주민의 신뢰받는 눈 건강 파트너임을 강조해주세요."
        ),
    },
]

SYSTEM_PROMPT = (
    "당신은 안과 전문 의학 블로그 작성 전문가입니다. "
    "제공된 최신 논문·기사를 근거로 의학적으로 정확하고 신뢰할 수 있는 정보를 제공하되, "
    "일반 독자가 쉽게 이해할 수 있는 친근한 문체로 작성합니다. "
    "반드시 다음 형식을 따르세요:\n\n"
    "제목: [매력적인 한국어 제목]\n\n"
    "[본문 800~1000자]\n\n"
    "해시태그: #태그1 #태그2 #태그3 #태그4 #태그5"
)


# ── RSS 피드에서 최신 기사 1건 가져오기 ─────────────────────────────────────────

def fetch_article(feed_urls: list[str]) -> dict:
    """RSS 피드에서 무작위로 기사 1건 반환. 실패 시 빈 dict."""
    random.shuffle(feed_urls)
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            entries = [e for e in feed.entries if e.get("title") and e.get("link")]
            if entries:
                entry = random.choice(entries[:10])
                summary = entry.get("summary", entry.get("description", ""))
                # HTML 태그 간단 제거
                import re
                summary = re.sub(r"<[^>]+>", " ", summary).strip()
                return {
                    "title": entry.title,
                    "link": entry.link,
                    "summary": summary[:600],
                    "source": feed.feed.get("title", "PubMed"),
                }
        except Exception as e:
            print(f"    RSS 오류 ({url}): {e}")
    return {}


# ── Unsplash 이미지 URL 가져오기 ─────────────────────────────────────────────────

def fetch_unsplash_image(query: str) -> str:
    """Unsplash에서 관련 이미지 URL 반환. 실패 시 빈 문자열."""
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
            return photo["urls"]["regular"]
    except Exception as e:
        print(f"    Unsplash 오류: {e}")
    return ""


# ── Claude로 한국어 블로그 글 생성 ───────────────────────────────────────────────

def generate_blog_post(client: anthropic.Anthropic, config: dict, article: dict) -> str:
    if article:
        article_context = (
            f"[참고 논문/기사]\n"
            f"제목: {article['title']}\n"
            f"출처: {article['source']}\n"
            f"내용 요약: {article['summary']}\n"
            f"원문 링크: {article['link']}\n\n"
        )
    else:
        article_context = ""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"카테고리: {config['category']}\n\n"
                    f"{article_context}"
                    f"{config['prompt_suffix']}\n\n"
                    "본문은 800~1000자, 마지막에 해시태그 5개를 포함해주세요."
                ),
            }
        ],
    )
    return message.content[0].text


# ── 전체 글 생성 ─────────────────────────────────────────────────────────────────

def generate_all_posts(client: anthropic.Anthropic) -> list[dict]:
    posts = []
    for config in TOPIC_CONFIGS:
        print(f"  - [{config['category']}] 기사 검색 중...")
        article = fetch_article(config["feed_urls"])

        print(f"  - [{config['category']}] 이미지 검색 중...")
        image_url = fetch_unsplash_image(config["unsplash_query"])

        print(f"  - [{config['category']}] 글 생성 중...")
        content = generate_blog_post(client, config, article)

        posts.append({
            "category": config["category"],
            "content": content,
            "article": article,
            "image_url": image_url,
        })
    return posts


# ── 이메일 HTML 구성 ──────────────────────────────────────────────────────────────

def build_email_html(posts: list[dict], generated_at: str) -> str:
    post_blocks = ""
    for i, post in enumerate(posts, 1):
        lines = post["content"].strip().split("\n")
        title_line = next((l for l in lines if l.startswith("제목:")), f"글 {i}")
        title = title_line.replace("제목:", "").strip()

        hashtag_line = next((l for l in lines if l.startswith("해시태그:")), "")
        hashtags = hashtag_line.replace("해시태그:", "").strip()

        body_lines = [
            l for l in lines
            if not l.startswith("제목:") and not l.startswith("해시태그:") and l.strip()
        ]
        body = "<br>".join(body_lines)

        article = post.get("article", {})
        image_url = post.get("image_url", "")

        # 이미지 블록
        image_block = ""
        if image_url:
            image_block = f"""
            <img src="{image_url}" alt="{title}"
                 style="width:100%; border-radius:6px; margin-bottom:16px;
                        object-fit:cover; max-height:260px;">
            """

        # 출처 + 원문 링크 블록
        source_block = ""
        if article:
            source_block = f"""
            <div style="margin-top:16px; padding:12px 16px; background:#f0f6ff;
                        border-radius:6px; font-size:13px; color:#555;">
                <span style="font-weight:600; color:#4A90D9;">출처:</span>
                {article.get('source', '')} &nbsp;|&nbsp;
                <a href="{article.get('link', '#')}" target="_blank"
                   style="color:#4A90D9; text-decoration:none; font-weight:600;">
                   원문 보기 →
                </a>
            </div>
            """

        post_blocks += f"""
        <div style="margin-bottom:40px; padding:24px; background:#fff;
                    border-radius:8px; border-left:4px solid #4A90D9;
                    box-shadow:0 2px 6px rgba(0,0,0,0.08);">
            <p style="margin:0 0 4px; font-size:12px; color:#888;">[{i}] {post['category']}</p>
            {image_block}
            <h2 style="margin:0 0 16px; font-size:20px; color:#1a1a2e;">{title}</h2>
            <p style="line-height:1.8; color:#333; font-size:15px;">{body}</p>
            <p style="margin-top:16px; font-size:13px; color:#4A90D9;">{hashtags}</p>
            {source_block}
        </div>
        """

    return f"""
    <html><body style="font-family:'Apple SD Gothic Neo',Arial,sans-serif;
                       background:#f0f4f8; padding:32px; margin:0;">
        <div style="max-width:680px; margin:0 auto;">
            <div style="background:linear-gradient(135deg,#1a1a2e,#4A90D9);
                        padding:28px 32px; border-radius:10px 10px 0 0; color:#fff;">
                <h1 style="margin:0; font-size:22px;">밀양성모안과 블로그 자동화</h1>
                <p style="margin:6px 0 0; font-size:13px; opacity:0.85;">
                    생성일시: {generated_at}
                </p>
            </div>
            <div style="padding:24px 0;">
                {post_blocks}
            </div>
            <p style="text-align:center; font-size:12px; color:#aaa; margin-top:16px;">
                이 메일은 Claude AI와 PubMed 최신 논문을 기반으로 자동 생성된 콘텐츠입니다.
            </p>
        </div>
    </body></html>
    """


# ── 이메일 발송 ───────────────────────────────────────────────────────────────────

def send_email(posts: list[dict], generated_at: str) -> None:
    html_body = build_email_html(posts, generated_at)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[밀양성모안과] 블로그 글 3편 — {generated_at}"
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())


# ── 메인 ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{generated_at}] 블로그 글 생성 시작")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    posts = generate_all_posts(client)

    print("이메일 발송 중...")
    send_email(posts, generated_at)

    print(f"완료: {TO_EMAIL} 으로 발송되었습니다.")


if __name__ == "__main__":
    main()
