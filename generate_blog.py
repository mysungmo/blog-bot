import os
import smtplib
import anthropic
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TO_EMAIL = os.environ["TO_EMAIL"]

MODEL = "claude-sonnet-4-20250514"

BLOG_TOPICS = [
    {
        "category": "안과 질환 정보",
        "prompt": (
            "최신 안과 질환에 관한 의학 블로그 글을 작성해주세요. "
            "백내장, 녹내장, 황반변성, 당뇨망막병증, 건성안 등 주요 안과 질환 중 하나를 선택하여 "
            "원인, 증상, 치료법, 예방법을 포함해 일반인이 이해하기 쉽게 설명해주세요. "
            "최신 의학 연구 동향도 간략히 언급해주세요."
        ),
    },
    {
        "category": "눈 건강 상식",
        "prompt": (
            "눈 건강을 지키는 실용적인 생활 습관에 관한 블로그 글을 작성해주세요. "
            "스마트폰·PC 사용 시 눈 보호법, 눈에 좋은 영양소, 올바른 눈 휴식법, "
            "계절별 눈 관리법 등 독자가 바로 실천할 수 있는 정보를 담아주세요. "
            "최신 연구나 안과학회 가이드라인을 근거로 작성해주세요."
        ),
    },
    {
        "category": "밀양성모안과 홍보",
        "prompt": (
            "경남 밀양에 위치한 밀양성모안과를 소개하는 블로그 글을 작성해주세요. "
            "안과 전문의의 정밀 검진, 최신 장비를 이용한 시력교정술(라식·라섹·렌즈삽입술), "
            "백내장·녹내장·망막 질환 치료, 소아 안과, 콘택트렌즈 처방 등 "
            "진료 서비스를 자연스럽게 홍보하고, 지역 주민의 눈 건강을 책임지는 "
            "신뢰할 수 있는 안과임을 강조해주세요."
        ),
    },
]

SYSTEM_PROMPT = (
    "당신은 안과 전문 의학 블로그 작성 전문가입니다. "
    "의학적으로 정확하고 신뢰할 수 있는 정보를 제공하되, "
    "일반 독자가 쉽게 이해할 수 있는 친근한 문체로 작성합니다. "
    "각 글은 반드시 다음 형식을 따라야 합니다:\n\n"
    "제목: [매력적인 제목]\n\n"
    "[본문 800~1000자]\n\n"
    "해시태그: #태그1 #태그2 #태그3 #태그4 #태그5"
)


def generate_blog_post(client: anthropic.Anthropic, topic: dict) -> str:
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"카테고리: {topic['category']}\n\n"
                    f"{topic['prompt']}\n\n"
                    "위 지침에 따라 블로그 글을 작성해주세요. "
                    "본문은 800~1000자 사이로 작성하고, 마지막에 관련 해시태그 5개를 추가해주세요."
                ),
            }
        ],
    )
    return message.content[0].text


def generate_all_posts(client: anthropic.Anthropic) -> list[dict]:
    posts = []
    for topic in BLOG_TOPICS:
        print(f"  - [{topic['category']}] 생성 중...")
        content = generate_blog_post(client, topic)
        posts.append({"category": topic["category"], "content": content})
    return posts


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

        post_blocks += f"""
        <div style="margin-bottom:40px; padding:24px; background:#fff;
                    border-radius:8px; border-left:4px solid #4A90D9;
                    box-shadow:0 2px 6px rgba(0,0,0,0.08);">
            <p style="margin:0 0 4px; font-size:12px; color:#888;">
                [{i}] {post['category']}
            </p>
            <h2 style="margin:0 0 16px; font-size:20px; color:#1a1a2e;">{title}</h2>
            <p style="line-height:1.8; color:#333; font-size:15px;">{body}</p>
            <p style="margin-top:16px; font-size:13px; color:#4A90D9;">{hashtags}</p>
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
                이 메일은 Claude AI가 자동 생성한 콘텐츠입니다.
            </p>
        </div>
    </body></html>
    """


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


def main() -> None:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{generated_at}] 블로그 글 생성 시작")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print("글 생성 중...")
    posts = generate_all_posts(client)

    print("이메일 발송 중...")
    send_email(posts, generated_at)

    print(f"완료: {TO_EMAIL} 으로 발송되었습니다.")


if __name__ == "__main__":
    main()
