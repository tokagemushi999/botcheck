# Dockerfile - Python 3.11-slim、uvicorn+bot両方起動
FROM python:3.11-slim

LABEL maintainer="BotCheck Team"
LABEL version="1.0.0"
LABEL description="Discord Bot/AI Detection System"

# 作業ディレクトリ設定
WORKDIR /app

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をまずコピー（キャッシュ効率化）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード全体をコピー
COPY . .

# データディレクトリ作成
RUN mkdir -p /app/data

# 実行権限付与
RUN chmod +x /app/docker-entrypoint.sh

# ポート公開（API: 8000）
EXPOSE 8000

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"

# エントリーポイント
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# デフォルトコマンド（API + Bot 両方起動）
CMD ["all"]