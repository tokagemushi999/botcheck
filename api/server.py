"""BotCheck API Server — FastAPI + SQLite (aiosqlite)"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple

import aiosqlite
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from analyzer.engine import analyze_messages

logger = logging.getLogger("botcheck-api")

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
    # auto_scan_enabled カラムを安全に追加
    try:
        await db.execute("ALTER TABLE settings ADD COLUMN auto_scan_enabled INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass  # already exists
    await db.commit()
    return db


# ---------------------------------------------------------------------------
# API Key 認証 & レート制限
# ---------------------------------------------------------------------------
_api_key_daily_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "date": ""})

API_RATE_LIMITS: Dict[str, int] = {"free": 100, "pro": 10000}


async def validate_api_key(x_api_key: Optional[str] = Header(None)) -> Dict[str, Any]:
    """X-API-Key ヘッダーを検証して key 情報を返す"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT key, guild_id, plan, created_at, last_used_at FROM api_keys WHERE key = ?",
        (x_api_key,),
    )
    if not rows:
        raise HTTPException(status_code=403, detail="Invalid API key")
    r = rows[0]
    key_info: Dict[str, Any] = {
        "key": r[0], "guild_id": r[1], "plan": r[2],
        "created_at": r[3], "last_used_at": r[4],
    }

    # daily rate limit check
    today = time.strftime("%Y-%m-%d")
    usage = _api_key_daily_usage[x_api_key]
    if usage["date"] != today:
        usage["date"] = today
        usage["count"] = 0
    limit = API_RATE_LIMITS.get(key_info["plan"], 100)
    if usage["count"] >= limit:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded ({limit}/day)")
    usage["count"] += 1

    # update last_used_at
    await db.execute("UPDATE api_keys SET last_used_at = ? WHERE key = ?", (int(time.time()), x_api_key))
    await db.commit()
    return key_info


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

# 静的ファイルの提供
STATIC_PATH = Path(__file__).resolve().parent.parent / "static"
if STATIC_PATH.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")


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


class PlanInfo(BaseModel):
    name: str
    display_name: str
    price: Optional[float]
    features: List[str]
    limits: Dict[str, Any]


class SubscriptionResponse(BaseModel):
    guild_id: str
    plan: str
    expires_at: Optional[int]
    vote_bonus_expires_at: Optional[int]
    created_at: int


class TopGGVoteWebhook(BaseModel):
    user: str
    type: str  # "upvote" or "test"
    is_weekend: bool = False
    query: Optional[str] = None


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """ランディングページ（Accept-Language で言語切替）"""
    accept_lang = request.headers.get("accept-language", "")
    # 日本語以外は英語版を返す
    if "ja" not in accept_lang:
        en_path = Path(__file__).resolve().parent.parent / "static" / "lp" / "en" / "index.html"
        if en_path.exists():
            return en_path.read_text(encoding="utf-8")
    lp_path = Path(__file__).resolve().parent.parent / "static" / "lp" / "index.html"
    if lp_path.exists():
        return lp_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>BotCheck</h1><p>Landing page not found</p>")


@app.get("/en", response_class=HTMLResponse)
@app.get("/en/", response_class=HTMLResponse)
async def landing_page_en():
    """英語LP"""
    en_path = Path(__file__).resolve().parent.parent / "static" / "lp" / "en" / "index.html"
    if en_path.exists():
        return en_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>BotCheck</h1><p>English landing page not found</p>")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Webダッシュボード"""
    return HTMLResponse(get_dashboard_html())


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


@app.get("/plans", response_model=List[PlanInfo])
async def get_plans():
    """利用可能なプラン一覧"""
    return [
        PlanInfo(
            name="free",
            display_name="Free",
            price=None,
            features=[
                "1サーバー/アカウント",
                "基本分析（総合スコアのみ）",
                "1日10回分析",
                "スキャン100件まで"
            ],
            limits={
                "max_servers_per_owner": 1,
                "max_analyses_per_day": 10,
                "scan_limit": 100,
                "detailed_scores": False,
                "api_access": False,
                "weekly_reports": False
            }
        ),
        PlanInfo(
            name="pro",
            display_name="Pro",
            price=5.0,
            features=[
                "無制限サーバー",
                "詳細分析（4エンジン個別スコア）",
                "無制限分析",
                "スキャン1000件",
                "APIアクセス",
                "週次レポート"
            ],
            limits={
                "max_servers_per_owner": 999999,
                "max_analyses_per_day": 999999,
                "scan_limit": 1000,
                "detailed_scores": True,
                "api_access": True,
                "weekly_reports": True
            }
        )
    ]


@app.get("/subscription/{guild_id}", response_model=SubscriptionResponse)
async def get_subscription(guild_id: str):
    """ギルドの現在のサブスクリプション情報"""
    db = await get_db()
    
    row = await db.execute_fetchall(
        """SELECT guild_id, plan, expires_at, vote_bonus_expires_at, created_at 
           FROM subscriptions WHERE guild_id = ?""",
        (guild_id,)
    )
    
    if not row:
        # 初回はフリープランで作成
        now = int(time.time())
        await db.execute(
            "INSERT INTO subscriptions (guild_id, plan) VALUES (?, 'free')",
            (guild_id,)
        )
        await db.commit()
        
        return SubscriptionResponse(
            guild_id=guild_id,
            plan="free",
            expires_at=None,
            vote_bonus_expires_at=None,
            created_at=now
        )
    
    r = row[0]
    return SubscriptionResponse(
        guild_id=r[0],
        plan=r[1],
        expires_at=r[2],
        vote_bonus_expires_at=r[3],
        created_at=r[4]
    )


@app.post("/subscription/{guild_id}/upgrade")
async def upgrade_subscription(guild_id: str):
    """プランアップグレード（モック実装）"""
    db = await get_db()
    now = int(time.time())
    expires_at = now + (30 * 86400)  # 30日後
    
    # サブスクリプションをProに更新（モック）
    await db.execute(
        """INSERT INTO subscriptions (guild_id, plan, expires_at, updated_at) 
           VALUES (?, 'pro', ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET
               plan = 'pro',
               expires_at = excluded.expires_at,
               updated_at = excluded.updated_at""",
        (guild_id, expires_at, now)
    )
    await db.commit()
    
    return {
        "success": True,
        "message": "モック: Proプランにアップグレードしました（30日間）",
        "expires_at": expires_at
    }


@app.post("/webhook/topgg")
async def topgg_webhook(vote_data: TopGGVoteWebhook):
    """top.ggからの投票webhook"""
    try:
        user_id = vote_data.user
        
        # 投票ボーナス: 24時間Pro機能を有効化
        now = int(time.time())
        bonus_expires_at = now + (24 * 3600)  # 24時間後
        
        # ユーザーが参加している全サーバーでボーナス適用
        # 実際の実装では、Discordから情報を取得する必要がある
        # ここではモック実装として、テスト用のguild_idを使用
        
        db = await get_db()
        
        # 投票ログを記録（後で実装予定）
        logger.info(f"top.gg vote received: user={user_id}, type={vote_data.type}")
        
        # 注意: 本番では適切なユーザー→ギルドマッピングが必要
        # 今回は基盤準備のみなので、実際の適用は後回し
        
        return {
            "success": True,
            "message": f"Vote bonus activated for user {user_id}",
            "bonus_duration_hours": 24
        }
    
    except Exception as e:
        logger.error(f"top.gg webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")


# ---------------------------------------------------------------------------
# Public API v1 (API Key 認証)
# ---------------------------------------------------------------------------

class V1CheckRequest(BaseModel):
    messages: List[Dict[str, Any]]
    weights: Optional[Dict[str, float]] = None


class V1CheckResponse(BaseModel):
    total_score: float
    timing_score: float
    style_score: float
    behavior_score: float
    ai_score: float
    confidence: float
    message_count: int


class V1UserScoreResponse(BaseModel):
    user_id: str
    total_score: float
    timing_score: float
    style_score: float
    behavior_score: float
    ai_score: float
    sample_size: int
    analyzed_at: int


@app.post("/api/v1/check", response_model=V1CheckResponse)
async def api_v1_check(req: V1CheckRequest, key_info: Dict[str, Any] = Depends(validate_api_key)):
    """Public API: Analyze messages and return bot-likelihood score."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    result = analyze_messages(req.messages, req.weights)
    return V1CheckResponse(
        total_score=result.total_score,
        timing_score=result.timing_score,
        style_score=result.style_score,
        behavior_score=result.behavior_score,
        ai_score=result.ai_score,
        confidence=result.confidence,
        message_count=result.message_count,
    )


@app.get("/api/v1/user/{user_id}/score", response_model=V1UserScoreResponse)
async def api_v1_user_score(user_id: str, key_info: Dict[str, Any] = Depends(validate_api_key)):
    """Public API: Get latest score for a user."""
    db = await get_db()
    row = await db.execute_fetchall(
        """SELECT user_id, total_score, timing_score, style_score, behavior_score,
                  ai_score, sample_size, analyzed_at
           FROM scores WHERE user_id = ? ORDER BY analyzed_at DESC LIMIT 1""",
        (user_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Score not found for this user")
    r = row[0]
    return V1UserScoreResponse(
        user_id=r[0], total_score=r[1], timing_score=r[2], style_score=r[3],
        behavior_score=r[4], ai_score=r[5], sample_size=r[6], analyzed_at=r[7],
    )


# ---------------------------------------------------------------------------
# API Key 管理エンドポイント (ダッシュボード用)
# ---------------------------------------------------------------------------

@app.post("/api/keys/generate")
async def generate_api_key(guild_id: str, plan: str = "free"):
    """APIキーを生成"""
    if plan not in ("free", "pro"):
        raise HTTPException(status_code=400, detail="Invalid plan")
    key = "bc_" + secrets.token_hex(24)
    db = await get_db()
    await db.execute(
        "INSERT INTO api_keys (key, guild_id, plan) VALUES (?, ?, ?)",
        (key, guild_id, plan),
    )
    await db.commit()
    return {"key": key, "guild_id": guild_id, "plan": plan}


@app.delete("/api/keys/{api_key}")
async def revoke_api_key(api_key: str):
    """APIキーを無効化"""
    db = await get_db()
    cursor = await db.execute("DELETE FROM api_keys WHERE key = ?", (api_key,))
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked"}


@app.get("/api/keys")
async def list_api_keys(guild_id: str):
    """ギルドのAPIキー一覧"""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT key, guild_id, plan, created_at, last_used_at FROM api_keys WHERE guild_id = ?",
        (guild_id,),
    )
    return [
        {"key": r[0][:8] + "...", "guild_id": r[1], "plan": r[2],
         "created_at": r[3], "last_used_at": r[4]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# HTML コンテンツ生成
# ---------------------------------------------------------------------------
def get_dashboard_html() -> str:
    """ダッシュボード用HTMLを生成"""
    return """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BotCheck Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #1e1e2e 0%, #2d1b69 100%);
            color: #e5e5e5;
            min-height: 100vh;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-value {
            font-size: 2.2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #b0b0b0;
            font-size: 1.1em;
        }

        .chart-container {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .user-list {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .user-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .user-item:last-child {
            border-bottom: none;
        }

        .user-score {
            font-weight: bold;
            padding: 5px 15px;
            border-radius: 20px;
        }

        .score-high { background: rgba(220, 38, 127, 0.3); color: #ff6b9d; }
        .score-medium { background: rgba(255, 159, 28, 0.3); color: #ffb347; }
        .score-low { background: rgba(34, 197, 94, 0.3); color: #60d394; }

        .loading {
            text-align: center;
            padding: 50px;
            color: #888;
        }

        .section-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #e5e5e5;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 BotCheck Dashboard</h1>
            <p>Discord Bot/AI検知システム</p>
        </div>

        <div id="loading" class="loading">
            <p>データを読み込み中...</p>
        </div>

        <div id="dashboard-content" style="display: none;">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="total-users">0</div>
                    <div class="stat-label">総ユーザー数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="total-messages">0</div>
                    <div class="stat-label">総メッセージ数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="total-analyses">0</div>
                    <div class="stat-label">分析実行数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-score">0</div>
                    <div class="stat-label">平均スコア</div>
                </div>
            </div>

            <div class="chart-container">
                <h2 class="section-title">スコア分布</h2>
                <canvas id="scoreChart" width="400" height="200"></canvas>
            </div>

            <div class="chart-container" style="margin-bottom:30px;">
                <h2 class="section-title">フィルター</h2>
                <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
                    <label style="color:#b0b0b0;font-size:14px;">サーバー:
                        <select id="guild-select" style="background:#1e1e2e;color:#e5e5e5;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:6px 12px;font-size:14px;">
                            <option value="">全サーバー</option>
                        </select>
                    </label>
                    <label style="color:#b0b0b0;font-size:14px;">期間:
                        <select id="period-select" style="background:#1e1e2e;color:#e5e5e5;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:6px 12px;font-size:14px;">
                            <option value="7">過去7日</option>
                            <option value="30" selected>過去30日</option>
                            <option value="90">過去90日</option>
                            <option value="">全期間</option>
                        </select>
                    </label>
                    <label style="color:#b0b0b0;font-size:14px;">スコア:
                        <input id="score-min" type="number" min="0" max="100" value="0" style="width:60px;background:#1e1e2e;color:#e5e5e5;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:6px 8px;font-size:14px;">
                        〜
                        <input id="score-max" type="number" min="0" max="100" value="100" style="width:60px;background:#1e1e2e;color:#e5e5e5;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:6px 8px;font-size:14px;">
                    </label>
                </div>
            </div>

            <div class="user-list">
                <h2 class="section-title">疑わしいユーザー Top10</h2>
                <div id="suspicious-users"></div>
            </div>

            <div class="chart-container" style="margin-top:30px;">
                <h2 class="section-title">🔑 APIキー管理</h2>
                <div style="margin-bottom:16px;">
                    <input id="apikey-guild" placeholder="Guild ID" style="background:#1e1e2e;color:#e5e5e5;border:1px solid rgba(255,255,255,0.2);border-radius:8px;padding:8px 12px;font-size:14px;width:200px;">
                    <button onclick="generateApiKey()" style="background:#667eea;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:14px;cursor:pointer;margin-left:8px;">キー生成</button>
                </div>
                <div id="api-keys-list" style="font-size:14px;color:#b0b0b0;"></div>
            </div>
        </div>
    </div>

    <script>
        // Dashboard JavaScript
        let scoreChart;

        async function loadDashboard() {
            try {
                const response = await fetch('/stats');
                const data = await response.json();
                
                // 統計更新
                document.getElementById('total-users').textContent = data.total_users.toLocaleString();
                document.getElementById('total-messages').textContent = data.total_messages.toLocaleString();
                document.getElementById('total-analyses').textContent = data.total_analyses.toLocaleString();
                document.getElementById('avg-score').textContent = data.avg_score ? data.avg_score.toFixed(1) : '0';

                // 疑わしいユーザーリスト
                const suspiciousContainer = document.getElementById('suspicious-users');
                if (data.top_suspicious.length === 0) {
                    suspiciousContainer.innerHTML = '<p style="color: #888; text-align: center; padding: 20px;">データがありません</p>';
                } else {
                    suspiciousContainer.innerHTML = data.top_suspicious.map(user => {
                        let scoreClass = 'score-low';
                        if (user.score >= 80) scoreClass = 'score-high';
                        else if (user.score >= 60) scoreClass = 'score-medium';

                        const date = new Date(user.analyzed_at * 1000).toLocaleDateString('ja-JP');
                        return `
                            <div class="user-item">
                                <div>
                                    <strong>${user.username}</strong><br>
                                    <small style="color: #888;">分析日: ${date}</small>
                                </div>
                                <div class="user-score ${scoreClass}">
                                    ${user.score}
                                </div>
                            </div>
                        `;
                    }).join('');
                }

                // スコア分布チャート（サンプルデータ）
                await createScoreChart(data.top_suspicious);

                // 表示切り替え
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard-content').style.display = 'block';
            } catch (error) {
                console.error('Error loading dashboard:', error);
                document.getElementById('loading').innerHTML = '<p style="color: #ff6b9d;">エラー: データの読み込みに失敗しました</p>';
            }
        }

        async function createScoreChart(users) {
            const ctx = document.getElementById('scoreChart').getContext('2d');
            
            // スコア範囲別にユーザーを集計
            const ranges = {
                '0-20': 0,
                '21-40': 0,
                '41-60': 0,
                '61-80': 0,
                '81-100': 0
            };

            users.forEach(user => {
                const score = user.score;
                if (score <= 20) ranges['0-20']++;
                else if (score <= 40) ranges['21-40']++;
                else if (score <= 60) ranges['41-60']++;
                else if (score <= 80) ranges['61-80']++;
                else ranges['81-100']++;
            });

            if (scoreChart) {
                scoreChart.destroy();
            }

            scoreChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['0-20 (人間)', '21-40 (正常)', '41-60 (やや疑)', '61-80 (要注意)', '81-100 (Bot/AI)'],
                    datasets: [{
                        label: 'ユーザー数',
                        data: Object.values(ranges),
                        backgroundColor: [
                            'rgba(96, 211, 148, 0.7)',
                            'rgba(96, 211, 148, 0.5)',
                            'rgba(255, 179, 71, 0.5)',
                            'rgba(255, 179, 71, 0.7)',
                            'rgba(255, 107, 157, 0.7)'
                        ],
                        borderColor: [
                            'rgba(96, 211, 148, 1)',
                            'rgba(96, 211, 148, 0.8)',
                            'rgba(255, 179, 71, 0.8)',
                            'rgba(255, 179, 71, 1)',
                            'rgba(255, 107, 157, 1)'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1,
                                color: '#e5e5e5'
                            },
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            }
                        },
                        x: {
                            ticks: {
                                color: '#e5e5e5'
                            },
                            grid: {
                                color: 'rgba(255, 255, 255, 0.1)'
                            }
                        }
                    }
                }
            });
        }

        // APIキー管理
        async function generateApiKey() {
            const guildId = document.getElementById('apikey-guild').value;
            if (!guildId) { alert('Guild IDを入力してください'); return; }
            const res = await fetch('/api/keys/generate?guild_id=' + guildId, {method:'POST'});
            const data = await res.json();
            alert('生成されたキー: ' + data.key);
            loadApiKeys(guildId);
        }

        async function loadApiKeys(guildId) {
            if (!guildId) return;
            const res = await fetch('/api/keys?guild_id=' + guildId);
            const keys = await res.json();
            const container = document.getElementById('api-keys-list');
            if (keys.length === 0) {
                container.innerHTML = '<p>APIキーがありません</p>';
            } else {
                container.innerHTML = keys.map(k =>
                    '<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.1);">' +
                    '<code>' + k.key + '</code> | ' + k.plan +
                    ' | 最終使用: ' + (k.last_used_at ? new Date(k.last_used_at*1000).toLocaleString('ja-JP') : '未使用') +
                    '</div>'
                ).join('');
            }
        }

        document.getElementById('apikey-guild')?.addEventListener('change', function() {
            loadApiKeys(this.value);
        });

        // ページ読み込み時にダッシュボードを読み込む
        document.addEventListener('DOMContentLoaded', loadDashboard);

        // 30秒ごとに自動更新
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 直接起動用
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
