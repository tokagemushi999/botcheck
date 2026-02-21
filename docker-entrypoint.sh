#!/bin/bash
set -e

# データベース初期化
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

echo "Starting BotCheck API + Discord Bot..."

# バックグラウンドでAPI起動
uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 1 &
API_PID=$!
echo "API started (PID: $API_PID)"

# SIGTERM/SIGINTをトラップ
cleanup() {
    echo "Received signal, shutting down..."
    kill $API_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

if [ -z "$DISCORD_TOKEN" ]; then
    echo "DISCORD_TOKEN not set. Running API only."
    wait $API_PID
else
    echo "Starting Discord bot in foreground..."
    python -m discord_bot.bot
    BOT_EXIT=$?
    echo "Bot process exited with code: $BOT_EXIT"
    kill $API_PID 2>/dev/null || true
    exit $BOT_EXIT
fi
