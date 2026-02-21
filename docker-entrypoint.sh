#!/bin/bash
# docker-entrypoint.sh - Docker起動スクリプト

set -e

# データベース初期化
init_database() {
    echo "Initializing database..."
    python -c "
import asyncio
from api.server import init_db
async def main():
    db = await init_db()
    await db.close()
    print('Database initialized successfully')
asyncio.run(main())
"
}

echo "Starting BotCheck API + Discord Bot..."

init_database

# バックグラウンドでAPI起動
uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 1 &
API_PID=$!

# SIGTERM/SIGINTをトラップ
trap "echo 'Shutting down...'; kill $API_PID 2>/dev/null; exit 0" SIGTERM SIGINT

if [ -z "$DISCORD_TOKEN" ]; then
    echo "DISCORD_TOKEN not set. Running API only."
    wait $API_PID
else
    # Botをフォアグラウンドで実行（これがメインプロセスになる）
    python -m discord_bot.bot
    # Botが終了したらAPIも停止
    echo "Bot process exited. Stopping API..."
    kill $API_PID 2>/dev/null || true
fi
