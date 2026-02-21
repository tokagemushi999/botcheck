PRAGMA foreign_keys = ON;

-- ユーザー基本情報
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT,
    is_bot INTEGER NOT NULL DEFAULT 0 CHECK (is_bot IN (0, 1)),
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 収集したメッセージ履歴
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    content_length INTEGER NOT NULL DEFAULT 0,
    mention_count INTEGER NOT NULL DEFAULT 0,
    emoji_count INTEGER NOT NULL DEFAULT 0,
    attachment_count INTEGER NOT NULL DEFAULT 0,
    reaction_count INTEGER NOT NULL DEFAULT 0,
    is_reply INTEGER NOT NULL DEFAULT 0 CHECK (is_reply IN (0, 1)),
    is_edited INTEGER NOT NULL DEFAULT 0 CHECK (is_edited IN (0, 1)),
    created_at INTEGER NOT NULL,
    edited_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- 分析スコア履歴
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    total_score REAL NOT NULL CHECK (total_score >= 0 AND total_score <= 100),
    timing_score REAL NOT NULL CHECK (timing_score >= 0 AND timing_score <= 100),
    style_score REAL NOT NULL CHECK (style_score >= 0 AND style_score <= 100),
    behavior_score REAL NOT NULL CHECK (behavior_score >= 0 AND behavior_score <= 100),
    ai_score REAL NOT NULL CHECK (ai_score >= 0 AND ai_score <= 100),
    sample_size INTEGER NOT NULL DEFAULT 0,
    analyzed_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- アラート履歴
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    score_id INTEGER,
    threshold REAL NOT NULL DEFAULT 80 CHECK (threshold >= 0 AND threshold <= 100),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    message TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    sent_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (score_id) REFERENCES scores (id) ON DELETE SET NULL
);

-- サーバー設定
CREATE TABLE IF NOT EXISTS settings (
    guild_id TEXT PRIMARY KEY,
    watch_enabled INTEGER NOT NULL DEFAULT 1 CHECK (watch_enabled IN (0, 1)),
    alert_threshold REAL NOT NULL DEFAULT 80 CHECK (alert_threshold >= 0 AND alert_threshold <= 100),
    min_messages_for_analysis INTEGER NOT NULL DEFAULT 20 CHECK (min_messages_for_analysis >= 1),
    weekly_report_channel_id TEXT,
    admin_user_id TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- サブスクリプション管理
CREATE TABLE IF NOT EXISTS subscriptions (
    guild_id TEXT PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    expires_at INTEGER,
    vote_bonus_expires_at INTEGER, -- top.gg投票ボーナス用
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_users_guild_last_seen ON users (guild_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_guild_created ON messages (guild_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_user_analyzed ON scores (user_id, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_guild_analyzed ON scores (guild_id, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status_created ON alerts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires ON subscriptions (expires_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON subscriptions (plan);
