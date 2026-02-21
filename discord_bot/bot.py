"""BotCheck Discord Bot — discord.py でメッセージ収集 + スラッシュコマンド"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN", "")
DB_PATH = os.getenv("BOTCHECK_DB", str(Path(__file__).resolve().parent.parent / "data" / "botcheck.db"))
API_URL = os.getenv("BOTCHECK_API_URL", "http://localhost:8000")
ALERT_THRESHOLD = float(os.getenv("BOTCHECK_ALERT_THRESHOLD", "80"))
MIN_MESSAGES = int(os.getenv("BOTCHECK_MIN_MESSAGES", "20"))

logger = logging.getLogger("botcheck")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------------------------------------------------------
# Bot セットアップ
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class BotCheckBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db: Optional[aiosqlite.Connection] = None

    async def setup_hook(self):
        """起動時にDB接続 & コマンド同期"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.db = await aiosqlite.connect(DB_PATH)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")

        schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")
        await self.db.executescript(schema)
        await self.db.commit()

        await self.add_cog(BotCheckCog(self))

    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()


bot = BotCheckBot()


# ---------------------------------------------------------------------------
# メッセージ収集
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"ログイン完了: {bot.user} (ID: {bot.user.id})")
    logger.info(f"サーバー数: {len(bot.guilds)}")
    # ギルドごとにコマンド同期（即時反映）
    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f"コマンド同期: {guild.name} ({len(synced)}個)")
    logger.info("全ギルド同期完了")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    db = bot.db
    if not db:
        return

    now = int(time.time())
    user = message.author

    # ユーザー upsert
    await db.execute(
        """INSERT INTO users (id, guild_id, username, display_name, is_bot, first_seen_at, last_seen_at)
           VALUES (?, ?, ?, ?, 0, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               username = excluded.username,
               display_name = excluded.display_name,
               last_seen_at = excluded.last_seen_at,
               updated_at = ?""",
        (
            str(user.id),
            str(message.guild.id) if message.guild else "",
            user.name,
            user.display_name,
            now,
            now,
            now,
        ),
    )

    # メッセージ保存
    emoji_count = len([c for c in message.content if ord(c) > 0x1F300])
    await db.execute(
        """INSERT OR IGNORE INTO messages
           (id, guild_id, channel_id, user_id, content, content_length,
            mention_count, emoji_count, attachment_count, reaction_count,
            is_reply, is_edited, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(message.id),
            str(message.guild.id) if message.guild else "",
            str(message.channel.id),
            str(user.id),
            message.content[:2000],
            len(message.content),
            len(message.mentions),
            emoji_count,
            len(message.attachments),
            0,  # リアクションは後でカウント
            1 if message.reference else 0,
            0,
            int(message.created_at.timestamp()),
        ),
    )
    await db.commit()

    await bot.process_commands(message)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """編集を記録"""
    if after.author.bot or not bot.db:
        return
    await bot.db.execute(
        "UPDATE messages SET is_edited = 1, edited_at = ? WHERE id = ?",
        (int(time.time()), str(after.id)),
    )
    await bot.db.commit()


@bot.event
async def on_guild_join(guild: discord.Guild):
    """ギルド参加時に全チャンネルの過去メッセージを自動スキャン"""
    logger.info(f"新しいギルドに参加: {guild.name} (ID: {guild.id})")

    # システムチャンネルを探す
    system_channel = guild.system_channel
    progress_channel = system_channel if system_channel and system_channel.permissions_for(guild.me).send_messages else None
    
    if progress_channel:
        try:
            embed = discord.Embed(
                title="🤖 BotCheck へようこそ！",
                description="このサーバーの過去メッセージを分析中です...",
                color=discord.Color.blurple()
            )
            embed.add_field(name="進捗", value="📊 スキャン開始", inline=False)
            progress_msg = await progress_channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"進捗メッセージ送信失敗: {e}")
            progress_msg = None
    else:
        progress_msg = None

    total_messages = 0
    total_users = set()
    scanned_channels = 0
    
    try:
        # 全テキストチャンネルをスキャン
        for channel in guild.text_channels:
            # Botに読み取り権限があるかチェック
            if not channel.permissions_for(guild.me).read_message_history:
                logger.info(f"チャンネル {channel.name} は権限不足でスキップ")
                continue

            channel_count = await _scan_guild_channel(channel, guild.id, bot.db)
            total_messages += channel_count
            scanned_channels += 1
            
            # 50チャンネルごとに進捗更新
            if progress_msg and scanned_channels % 5 == 0:
                try:
                    embed = discord.Embed(
                        title="🤖 BotCheck セットアップ中",
                        description=f"チャンネルを分析しています...",
                        color=discord.Color.blurple()
                    )
                    embed.add_field(
                        name="進捗", 
                        value=f"📊 {scanned_channels} チャンネル完了\n📨 {total_messages} メッセージ収集", 
                        inline=False
                    )
                    await progress_msg.edit(embed=embed)
                except Exception as e:
                    logger.warning(f"進捗更新失敗: {e}")

        logger.info(f"ギルド {guild.name} のスキャン完了: {total_messages}件のメッセージ, {scanned_channels}チャンネル")

        # 完了通知
        if progress_msg:
            try:
                embed = discord.Embed(
                    title="✅ BotCheck セットアップ完了！",
                    description="このサーバーの過去メッセージの分析が完了しました。",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="結果", 
                    value=f"📊 **{scanned_channels}** チャンネルをスキャン\n"
                          f"📨 **{total_messages}** メッセージを収集\n"
                          f"🔍 `/botcheck` コマンドでユーザー分析が可能です", 
                    inline=False
                )
                embed.set_footer(text="BotCheck は自動でBot/AIアカウントを検知します")
                await progress_msg.edit(embed=embed)
            except Exception as e:
                logger.warning(f"完了通知送信失敗: {e}")

    except Exception as e:
        logger.error(f"ギルドスキャン中にエラー: {e}", exc_info=True)
        if progress_msg:
            try:
                embed = discord.Embed(
                    title="⚠️ スキャンでエラーが発生",
                    description=f"一部のチャンネルをスキップしました: {str(e)[:200]}",
                    color=discord.Color.orange()
                )
                embed.add_field(name="収集済み", value=f"{total_messages} メッセージ", inline=False)
                await progress_msg.edit(embed=embed)
            except Exception:
                pass


async def _scan_guild_channel(channel: discord.TextChannel, guild_id: str, db: aiosqlite.Connection, limit: int = 500) -> int:
    """指定チャンネルの過去メッセージをDBに取り込み（on_guild_join用）"""
    count = 0
    now = int(time.time())
    
    try:
        async for message in channel.history(limit=limit):
            if message.author.bot:
                continue

            user = message.author

            # ユーザー upsert
            await db.execute(
                """INSERT INTO users (id, guild_id, username, display_name, is_bot, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       username = excluded.username,
                       display_name = excluded.display_name,
                       last_seen_at = MAX(excluded.last_seen_at, users.last_seen_at),
                       updated_at = ?""",
                (str(user.id), guild_id, user.name, user.display_name,
                 int(message.created_at.timestamp()), int(message.created_at.timestamp()), now),
            )

            # メッセージ保存
            emoji_count = len([c for c in message.content if ord(c) > 0x1F300])
            await db.execute(
                """INSERT OR IGNORE INTO messages
                   (id, guild_id, channel_id, user_id, content, content_length,
                    mention_count, emoji_count, attachment_count, reaction_count,
                    is_reply, is_edited, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(message.id), guild_id, str(channel.id), str(user.id),
                 message.content[:2000], len(message.content),
                 len(message.mentions), emoji_count, len(message.attachments),
                 sum(r.count for r in message.reactions) if message.reactions else 0,
                 1 if message.reference else 0,
                 1 if message.edited_at else 0,
                 int(message.created_at.timestamp())),
            )
            count += 1

        await db.commit()
        
    except Exception as e:
        logger.warning(f"チャンネル {channel.name} のスキャン中にエラー: {e}")
    
    return count


# ---------------------------------------------------------------------------
# スラッシュコマンド
# ---------------------------------------------------------------------------
class BotCheckCog(commands.Cog):
    def __init__(self, bot: BotCheckBot):
        self.bot = bot

    @property
    def db(self) -> aiosqlite.Connection:
        assert self.bot.db is not None
        return self.bot.db

    @app_commands.command(name="botcheck", description="ユーザーのBot度を分析")
    @app_commands.describe(
        user="分析対象のユーザー",
        action="実行するアクション",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="ユーザー分析", value="user"),
        app_commands.Choice(name="サーバー全体", value="server"),
        app_commands.Choice(name="監視ON/OFF", value="watch"),
        app_commands.Choice(name="週次レポート", value="report"),
        app_commands.Choice(name="過去メッセージ取込", value="scan"),
    ])
    async def botcheck(
        self,
        interaction: discord.Interaction,
        action: str = "user",
        user: Optional[discord.Member] = None,
    ):
        if action == "user":
            await self._analyze_user(interaction, user or interaction.user)
        elif action == "server":
            await self._server_summary(interaction)
        elif action == "watch":
            await self._toggle_watch(interaction)
        elif action == "report":
            await self._weekly_report(interaction)
        elif action == "scan":
            await self._scan_channel(interaction)

    async def _analyze_user(self, interaction: discord.Interaction, member: discord.Member | discord.User):
        """特定ユーザーのBot度スコアを表示"""
        await interaction.response.defer(thinking=True)

        user_id = str(member.id)
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""

        # DBからメッセージ取得
        rows = await self.db.execute_fetchall(
            """SELECT content, content_length, mention_count, emoji_count,
                      reaction_count, is_reply, is_edited, created_at, channel_id
               FROM messages WHERE user_id = ? AND guild_id = ?
               ORDER BY created_at DESC LIMIT 200""",
            (user_id, guild_id),
        )

        if len(rows) < MIN_MESSAGES:
            await interaction.followup.send(
                f"⚠️ {member.display_name} のメッセージが {len(rows)} 件しかありません（最低 {MIN_MESSAGES} 件必要）"
            )
            return

        # メッセージを分析用dictに変換
        messages = [
            {
                "content": r[0],
                "content_length": r[1],
                "mention_count": r[2],
                "emoji_count": r[3],
                "reaction_count": r[4],
                "is_reply": bool(r[5]),
                "is_edited": bool(r[6]),
                "created_at": r[7],
                "channel_id": r[8],
            }
            for r in rows
        ]

        from analyzer.engine import analyze_messages
        result = analyze_messages(messages)

        # スコアをDBに保存
        await self.db.execute(
            """INSERT INTO scores (guild_id, user_id, total_score, timing_score,
               style_score, behavior_score, ai_score, sample_size)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, result.total_score, result.timing_score,
             result.style_score, result.behavior_score, result.ai_score,
             result.message_count),
        )
        await self.db.commit()

        # スコアに応じた色
        if result.total_score >= 80:
            color = discord.Color.red()
            verdict = "🚨 高確率でBot/AI"
        elif result.total_score >= 60:
            color = discord.Color.orange()
            verdict = "⚠️ 要注意"
        elif result.total_score >= 40:
            color = discord.Color.yellow()
            verdict = "🤔 やや疑わしい"
        else:
            color = discord.Color.green()
            verdict = "✅ 人間らしい"

        embed = discord.Embed(
            title=f"BotCheck: {member.display_name}",
            description=verdict,
            color=color,
        )
        embed.add_field(name="総合スコア", value=f"**{result.total_score}** / 100", inline=False)
        embed.add_field(name="⏱ タイミング", value=f"{result.timing_score}", inline=True)
        embed.add_field(name="✍️ 文体", value=f"{result.style_score}", inline=True)
        embed.add_field(name="🔄 行動", value=f"{result.behavior_score}", inline=True)
        embed.add_field(name="🤖 AI検知", value=f"{result.ai_score}", inline=True)
        embed.add_field(name="信頼度", value=f"{result.confidence}%", inline=True)
        embed.add_field(name="分析件数", value=f"{result.message_count} 件", inline=True)
        embed.set_footer(text="スコアが高いほどBot/AIの可能性が高い")

        await interaction.followup.send(embed=embed)

        # アラート判定
        if result.total_score >= ALERT_THRESHOLD and interaction.guild:
            await self._send_alert(interaction.guild, member, result.total_score)

    async def _scan_channel(self, interaction: discord.Interaction):
        """チャンネルの過去メッセージを一括取り込み"""
        await interaction.response.defer(thinking=True)

        channel = interaction.channel
        if not channel or not hasattr(channel, 'history'):
            await interaction.followup.send("❌ このチャンネルではスキャンできません")
            return

        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        count = 0
        user_set = set()
        now = int(time.time())

        async for message in channel.history(limit=1000):
            if message.author.bot:
                continue

            user = message.author
            user_set.add(user.id)

            # ユーザー upsert
            await self.db.execute(
                """INSERT INTO users (id, guild_id, username, display_name, is_bot, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       username = excluded.username,
                       display_name = excluded.display_name,
                       last_seen_at = MAX(excluded.last_seen_at, users.last_seen_at),
                       updated_at = ?""",
                (str(user.id), guild_id, user.name, user.display_name,
                 int(message.created_at.timestamp()), int(message.created_at.timestamp()), now),
            )

            # メッセージ保存
            emoji_count = len([c for c in message.content if ord(c) > 0x1F300])
            await self.db.execute(
                """INSERT OR IGNORE INTO messages
                   (id, guild_id, channel_id, user_id, content, content_length,
                    mention_count, emoji_count, attachment_count, reaction_count,
                    is_reply, is_edited, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(message.id), guild_id, str(channel.id), str(user.id),
                 message.content[:2000], len(message.content),
                 len(message.mentions), emoji_count, len(message.attachments),
                 sum(r.count for r in message.reactions) if message.reactions else 0,
                 1 if message.reference else 0,
                 1 if message.edited_at else 0,
                 int(message.created_at.timestamp())),
            )
            count += 1

        await self.db.commit()

        await interaction.followup.send(
            f"✅ スキャン完了！\n"
            f"📨 **{count}** 件のメッセージを取り込みました\n"
            f"👤 **{len(user_set)}** 人のユーザーを検出\n"
            f"📢 チャンネル: #{channel.name}"
        )

    async def _server_summary(self, interaction: discord.Interaction):
        """サーバー全体のサマリー"""
        await interaction.response.defer(thinking=True)

        guild_id = str(interaction.guild_id) if interaction.guild_id else ""

        # 最新スコア上位10名
        rows = await self.db.execute_fetchall(
            """SELECT s.user_id, u.username, s.total_score, s.sample_size
               FROM scores s
               LEFT JOIN users u ON s.user_id = u.id
               WHERE s.guild_id = ? AND s.id IN (
                   SELECT MAX(id) FROM scores WHERE guild_id = ? GROUP BY user_id
               )
               ORDER BY s.total_score DESC LIMIT 10""",
            (guild_id, guild_id),
        )

        if not rows:
            await interaction.followup.send("📊 まだ分析データがありません。`/botcheck user` で分析してください。")
            return

        stats = await self.db.execute_fetchall(
            "SELECT COUNT(DISTINCT user_id), COUNT(*) FROM messages WHERE guild_id = ?",
            (guild_id,),
        )

        embed = discord.Embed(
            title="📊 BotCheck サーバーサマリー",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="統計",
            value=f"ユーザー: {stats[0][0]} 人\nメッセージ: {stats[0][1]} 件",
            inline=False,
        )

        leaderboard = []
        for i, r in enumerate(rows, 1):
            icon = "🚨" if r[2] >= 80 else "⚠️" if r[2] >= 60 else "🤔" if r[2] >= 40 else "✅"
            leaderboard.append(f"{i}. {icon} **{r[1] or 'unknown'}** — {r[2]} ({r[3]}件)")

        embed.add_field(
            name="疑わしいユーザー Top10",
            value="\n".join(leaderboard) or "なし",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    async def _toggle_watch(self, interaction: discord.Interaction):
        """リアルタイム監視の切り替え"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者権限が必要です", ephemeral=True)
            return

        guild_id = str(interaction.guild_id)
        row = await self.db.execute_fetchall(
            "SELECT watch_enabled FROM settings WHERE guild_id = ?", (guild_id,)
        )

        if row:
            new_state = 0 if row[0][0] else 1
            await self.db.execute(
                "UPDATE settings SET watch_enabled = ?, updated_at = ? WHERE guild_id = ?",
                (new_state, int(time.time()), guild_id),
            )
        else:
            new_state = 1
            await self.db.execute(
                "INSERT INTO settings (guild_id, watch_enabled) VALUES (?, ?)",
                (guild_id, new_state),
            )

        await self.db.commit()
        state_text = "🟢 ON" if new_state else "🔴 OFF"
        await interaction.response.send_message(f"監視モード: {state_text}")

    async def _weekly_report(self, interaction: discord.Interaction):
        """週次レポート生成"""
        await interaction.response.defer(thinking=True)

        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        week_ago = int(time.time()) - 7 * 86400

        rows = await self.db.execute_fetchall(
            """SELECT s.user_id, u.username, AVG(s.total_score) as avg_score,
                      COUNT(*) as analyses
               FROM scores s
               LEFT JOIN users u ON s.user_id = u.id
               WHERE s.guild_id = ? AND s.analyzed_at >= ?
               GROUP BY s.user_id
               ORDER BY avg_score DESC LIMIT 15""",
            (guild_id, week_ago),
        )

        new_messages = await self.db.execute_fetchall(
            "SELECT COUNT(*) FROM messages WHERE guild_id = ? AND created_at >= ?",
            (guild_id, week_ago),
        )

        embed = discord.Embed(
            title="📋 週次BotCheckレポート",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="今週の統計",
            value=f"新規メッセージ: {new_messages[0][0]} 件\n分析実行: {len(rows)} ユーザー",
            inline=False,
        )

        if rows:
            lines = []
            for r in rows:
                icon = "🚨" if r[2] >= 80 else "⚠️" if r[2] >= 60 else "✅"
                lines.append(f"{icon} **{r[1] or 'unknown'}** — 平均 {r[2]:.1f} ({r[3]}回分析)")
            embed.add_field(name="ユーザー別", value="\n".join(lines), inline=False)

        await interaction.followup.send(embed=embed)

    async def _send_alert(self, guild: discord.Guild, member: discord.Member | discord.User, score: float):
        """管理者にアラートDM送信"""
        try:
            guild_id = str(guild.id)
            row = await self.db.execute_fetchall(
                "SELECT admin_user_id FROM settings WHERE guild_id = ?", (guild_id,)
            )
            if row and row[0][0]:
                admin = guild.get_member(int(row[0][0]))
                if admin:
                    await admin.send(
                        f"🚨 **BotCheck アラート**\n"
                        f"サーバー: {guild.name}\n"
                        f"ユーザー: {member.display_name} ({member.id})\n"
                        f"Bot度スコア: **{score}** / 100"
                    )

            # アラート記録
            await self.db.execute(
                """INSERT INTO alerts (guild_id, user_id, threshold, status, message)
                   VALUES (?, ?, ?, 'sent', ?)""",
                (guild_id, str(member.id), ALERT_THRESHOLD,
                 f"Score {score} exceeded threshold {ALERT_THRESHOLD}"),
            )
            await self.db.commit()
        except Exception as e:
            logger.warning(f"アラート送信失敗: {e}")


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.error("DISCORD_TOKEN が設定されていません。.env ファイルを確認してください。")
        return
    try:
        logger.info("Bot starting with bot.run()...")
        bot.run(TOKEN)
        logger.info("bot.run() returned normally")
    except Exception as e:
        logger.error(f"bot.run() raised exception: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
