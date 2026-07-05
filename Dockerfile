# Lease Guide(전월세 길잡이) MCP 서버 — PlayMCP in KC Git 소스 빌드용.
# ⚠️ linux/amd64 로 빌드되어야 함(arm64 는 서버 활성화 실패). 컨테이너 이미지 방식 폴백 시:
#    docker build --platform linux/amd64 -t lease-guide .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 런타임에 필요한 것만 복사 (serviceKey/.env 는 레포에 없음 → 이미지에 유입 불가)
COPY ingest/ ingest/
COPY domain/ domain/
COPY server/ server/
COPY data/lease.db data/lease.db

ENV PORT=8000
EXPOSE 8000

# streamable-http, remote, stateless (constitution §1)
CMD ["python", "-m", "server.app"]
