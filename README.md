# 밀양성모안과 블로그 자동화 시스템

Claude AI를 이용해 안과 블로그 글 3편을 자동 생성하고 Gmail로 발송하는 시스템입니다.
매주 **월·수·금 오전 9시(KST)** 에 GitHub Actions가 자동 실행합니다.

---

## 생성되는 글 구성

| # | 카테고리 | 내용 |
|---|----------|------|
| 1 | 안과 질환 정보 | 백내장·녹내장·황반변성 등 주요 질환 설명 |
| 2 | 눈 건강 상식 | 생활 속 눈 보호법, 영양, 휴식법 |
| 3 | 밀양성모안과 홍보 | 진료 서비스 소개 및 병원 홍보 |

각 글: **제목 + 본문 800~1000자 + 해시태그 5개**

---

## 설정 방법

### 1단계 — GitHub 저장소 생성 및 코드 업로드

```bash
git init
git add .
git commit -m "init: 블로그 자동화 시스템"
git remote add origin https://github.com/<계정>/<저장소명>.git
git push -u origin main
```

### 2단계 — GitHub Secrets 등록

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `ANTHROPIC_API_KEY` | Anthropic 콘솔에서 발급한 API 키 |
| `GMAIL_USER` | 발송에 사용할 Gmail 주소 (예: `you@gmail.com`) |
| `GMAIL_PASSWORD` | Gmail **앱 비밀번호** (일반 로그인 비밀번호 ❌) |
| `TO_EMAIL` | 블로그 글을 받을 이메일 주소 |

> **Gmail 앱 비밀번호 발급 방법**
> Google 계정 → 보안 → 2단계 인증 활성화 →
> 앱 비밀번호 → 앱: `메일`, 기기: `Windows 컴퓨터` → 생성

### 3단계 — 자동 실행 확인

- GitHub 저장소 → **Actions** 탭에서 워크플로 실행 기록 확인
- 수동 테스트: Actions → `밀양성모안과 블로그 자동 생성` → **Run workflow**

---

## 로컬 테스트

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY="sk-ant-..."
export GMAIL_USER="your@gmail.com"
export GMAIL_PASSWORD="앱비밀번호16자리"
export TO_EMAIL="receive@email.com"

python generate_blog.py
```

---

## 스케줄 정보

```
cron: "0 0 * * 1,3,5"
```

| UTC | KST |
|-----|-----|
| 매주 월·수·금 00:00 | 매주 월·수·금 09:00 |

---

## 파일 구조

```
.
├── generate_blog.py              # 글 생성 + 이메일 발송
├── .github/
│   └── workflows/
│       └── schedule.yml          # GitHub Actions 스케줄
├── requirements.txt
└── README.md
```
