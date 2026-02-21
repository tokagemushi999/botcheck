"""BotCheck API Server — FastAPI + SQLite (aiosqlite)"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Dict, List

import aiosqlite
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from analyzer.engine import analyze_messages

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("BOTCHECK_DB", str(Path(__file__).resolve().parent.parent / "data" / "botcheck.db"))
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

# レート制限設定
limiter = Limiter(key_func=get_remote_address)
RATE_LIMIT = "60/minute"  # 60リクエスト/分

# ---------------------------------------------------------------------------
# DB ヘルパー
# ---------------------------------------------------------------------------
_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    assert _db is not None, "DB not initialized"
    return _db


async def init_db() -> aiosqlite.Connection:
    """DB初期化 — schema.sql を実行"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    await db.executescript(schema)
    await db.commit()
    return db


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db
    _db = await init_db()
    yield
    if _db:
        await _db.close()
        _db = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="BotCheck API",
    description="Discord Bot/AI検知エンジン",
    version="1.0.0",
    lifespan=lifespan,
)

# レート制限の設定
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------
class MessageInput(BaseModel):
    content: str = ""
    created_at: Optional[int] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None
    is_reply: bool = False
    is_edited: bool = False
    mention_count: int = 0
    emoji_count: int = 0
    reaction_count: int = 0
    reply_delay_seconds: Optional[float] = None


class AnalyzeRequest(BaseModel):
    messages: List[Dict[str, Any]]
    weights: Optional[Dict[str, float]] = None
    guild_id: Optional[str] = None
    user_id: Optional[str] = None


class ScoreResponse(BaseModel):
    total_score: float
    timing_score: float
    style_score: float
    behavior_score: float
    ai_score: float
    confidence: float
    message_count: int
    details: Dict[str, Any] = Field(default_factory=dict)


class UserScoreRow(BaseModel):
    id: int
    total_score: float
    timing_score: float
    style_score: float
    behavior_score: float
    ai_score: float
    sample_size: int
    analyzed_at: int


class StatsResponse(BaseModel):
    total_users: int
    total_messages: int
    total_analyses: int
    avg_score: Optional[float]
    top_suspicious: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "ok", "timestamp": int(time.time())}


@app.post("/analyze", response_model=ScoreResponse)
@limiter.limit(RATE_LIMIT)
async def analyze(request: Request, req: AnalyzeRequest):
    """メッセージ配列を受け取りBot度スコアを返却"""
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages は空にできません")

    result = analyze_messages(req.messages, req.weights)

    # スコアをDBに保存（user_id & guild_id がある場合）
    if req.user_id and req.guild_id:
        db = await get_db()
        await db.execute(
            """INSERT INTO scores (guild_id, user_id, total_score, timing_score,
               style_score, behavior_score, ai_score, sample_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                req.guild_id,
                req.user_id,
                result.total_score,
                result.timing_score,
                result.style_score,
                result.behavior_score,
                result.ai_score,
                result.message_count,
            ),
        )
        await db.commit()

    return ScoreResponse(**result.to_dict())


@app.get("/user/{user_id}/score")
async def get_user_score(user_id: str):
    """ユーザーの最新スコアを取得"""
    db = await get_db()
    row = await db.execute_fetchall(
        """SELECT id, total_score, timing_score, style_score, behavior_score,
                  ai_score, sample_size, analyzed_at
           FROM scores WHERE user_id = ? ORDER BY analyzed_at DESC LIMIT 1""",
        (user_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="スコアが見つかりません")

    r = row[0]
    return UserScoreRow(
        id=r[0], total_score=r[1], timing_score=r[2], style_score=r[3],
        behavior_score=r[4], ai_score=r[5], sample_size=r[6], analyzed_at=r[7],
    )


@app.get("/user/{user_id}/history")
async def get_user_history(user_id: str, limit: int = 20):
    """ユーザーのスコア履歴"""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT id, total_score, timing_score, style_score, behavior_score,
                  ai_score, sample_size, analyzed_at
           FROM scores WHERE user_id = ? ORDER BY analyzed_at DESC LIMIT ?""",
        (user_id, min(limit, 100)),
    )
    return [
        UserScoreRow(
            id=r[0], total_score=r[1], timing_score=r[2], style_score=r[3],
            behavior_score=r[4], ai_score=r[5], sample_size=r[6], analyzed_at=r[7],
        )
        for r in rows
    ]


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """全体統計"""
    db = await get_db()

    users = await db.execute_fetchall("SELECT COUNT(*) FROM users")
    messages = await db.execute_fetchall("SELECT COUNT(*) FROM messages")
    analyses = await db.execute_fetchall("SELECT COUNT(*) FROM scores")
    avg = await db.execute_fetchall("SELECT AVG(total_score) FROM scores")

    # 疑わしいユーザー上位10件（最新スコア基準）
    top = await db.execute_fetchall(
        """SELECT s.user_id, u.username, s.total_score, s.analyzed_at
           FROM scores s
           LEFT JOIN users u ON s.user_id = u.id
           WHERE s.id IN (
               SELECT MAX(id) FROM scores GROUP BY user_id
           )
           ORDER BY s.total_score DESC LIMIT 10""",
    )

    return StatsResponse(
        total_users=users[0][0],
        total_messages=messages[0][0],
        total_analyses=analyses[0][0],
        avg_score=round(avg[0][0], 2) if avg[0][0] else None,
        top_suspicious=[
            {
                "user_id": r[0],
                "username": r[1] or "unknown",
                "score": r[2],
                "analyzed_at": r[3],
            }
            for r in top
        ],
    )


# ---------------------------------------------------------------------------
# 直接起動用
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
