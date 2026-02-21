#!/bin/bash
# docker-entrypoint.sh - Docker起動スクリプト

set -e

# 環境変数チェック
check_env_vars() {
    if [ -z "$DISCORD_TOKEN" ]; then
        echo "WARNING: DISCORD_TOKEN is not set. Bot functionality will be disabled."
    fi
}

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

# API サーバー起動
start_api() {
    echo "Starting BotCheck API server..."
    uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 1
}

# Discord Bot 起動
start_bot() {
    echo "Starting Discord Bot..."
    if [ -z "$DISCORD_TOKEN" ]; then
        echo "ERROR: DISCORD_TOKEN not set. Cannot start bot."
        exit 1
    fi
    python -m discord_bot.bot
}

# API + Bot 両方起動（並行処理）
start_all() {
    echo "Starting BotCheck API + Discord Bot..."
    
    # バックグラウンドでAPI起動
    uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 1 &
    API_PID=$!
    
    # Discord Bot起動
    if [ ! -z "$DISCORD_TOKEN" ]; then
        python -m discord_bot.bot &
        BOT_PID=$!
        
        # 両方のプロセスを監視
        wait_for_processes() {
            while kill -0 $API_PID 2>/dev/null && kill -0 $BOT_PID 2>/dev/null; do
                sleep 10
            done
            
            # どちらか一方が終了したら、もう一方も終了
            echo "One of the processes stopped. Shutting down..."
            kill $API_PID 2>/dev/null || true
            kill $BOT_PID 2>/dev/null || true
            wait
        }
        
        wait_for_processes
    else
        echo "DISCORD_TOKEN not set. Running API only."
        wait $API_PID
    fi
}

# メイン処理
main() {
    check_env_vars
    init_database
    
    case "$1" in
        "api")
            start_api
            ;;
        "bot")
            start_bot
            ;;
        "all"|"")
            start_all
            ;;
        *)
            echo "Usage: $0 {api|bot|all}"
            echo "  api  - Start API server only"
            echo "  bot  - Start Discord bot only"
            echo "  all  - Start both API and bot (default)"
            exit 1
            ;;
    esac
}

# スクリプト実行
main "$@"