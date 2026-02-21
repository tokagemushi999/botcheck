# SystemD 設定ガイド

BotCheck を Linux サーバーで systemd サービスとして実行する設定です。

## インストール手順

### 1. ユーザーとディレクトリの作成

```bash
# botcheck 専用ユーザーの作成
sudo useradd -r -s /bin/false -d /opt/botcheck botcheck

# アプリケーションディレクトリの作成
sudo mkdir -p /opt/botcheck
sudo chown botcheck:botcheck /opt/botcheck

# プロジェクトファイルのコピー
sudo cp -r /path/to/botcheck/* /opt/botcheck/
sudo chown -R botcheck:botcheck /opt/botcheck
```

### 2. Python 環境の準備

```bash
# Python 仮想環境の作成
sudo -u botcheck python3 -m venv /opt/botcheck/venv

# 依存関係のインストール
sudo -u botcheck /opt/botcheck/venv/bin/pip install -r /opt/botcheck/requirements.txt
```

### 3. 設定ファイルの準備

```bash
# .env ファイルの作成
sudo -u botcheck cp /opt/botcheck/.env.example /opt/botcheck/.env

# DISCORD_TOKEN を設定
sudo -u botcheck nano /opt/botcheck/.env
```

### 4. systemd サービスファイルのインストール

```bash
# サービスファイルのコピー
sudo cp /opt/botcheck/deploy/systemd/botcheck-api.service /etc/systemd/system/
sudo cp /opt/botcheck/deploy/systemd/botcheck-bot.service /etc/systemd/system/

# systemd 設定の再読み込み
sudo systemctl daemon-reload
```

### 5. サービスの有効化と開始

```bash
# API サービスの開始
sudo systemctl enable botcheck-api
sudo systemctl start botcheck-api

# Bot サービスの開始（API サービス起動後）
sudo systemctl enable botcheck-bot
sudo systemctl start botcheck-bot
```

## 管理コマンド

### サービス状態の確認

```bash
# サービス状態
sudo systemctl status botcheck-api
sudo systemctl status botcheck-bot

# ログの確認
sudo journalctl -u botcheck-api -f
sudo journalctl -u botcheck-bot -f

# 両方のログを同時に
sudo journalctl -u botcheck-api -u botcheck-bot -f
```

### サービスの制御

```bash
# 開始
sudo systemctl start botcheck-api
sudo systemctl start botcheck-bot

# 停止
sudo systemctl stop botcheck-bot
sudo systemctl stop botcheck-api

# 再起動
sudo systemctl restart botcheck-api
sudo systemctl restart botcheck-bot

# 設定リロード
sudo systemctl reload botcheck-api
sudo systemctl reload botcheck-bot
```

### 自動起動の設定

```bash
# 自動起動を有効
sudo systemctl enable botcheck-api
sudo systemctl enable botcheck-bot

# 自動起動を無効
sudo systemctl disable botcheck-api
sudo systemctl disable botcheck-bot
```

## ファイル構成

```
/opt/botcheck/
├── api/                    # FastAPI アプリケーション
├── analyzer/              # 分析エンジン
├── discord_bot/           # Discord Bot
├── data/                  # SQLite データベース
├── logs/                  # アプリケーションログ
├── venv/                  # Python 仮想環境
├── .env                   # 環境変数
└── requirements.txt       # Python 依存関係
```

## トラブルシューティング

### サービスが起動しない場合

1. **ログを確認**:
   ```bash
   sudo journalctl -u botcheck-api --no-pager
   sudo journalctl -u botcheck-bot --no-pager
   ```

2. **ファイル権限を確認**:
   ```bash
   sudo chown -R botcheck:botcheck /opt/botcheck
   sudo chmod +x /opt/botcheck/venv/bin/*
   ```

3. **依存関係を確認**:
   ```bash
   sudo -u botcheck /opt/botcheck/venv/bin/pip list
   ```

### API が応答しない場合

1. **ポートの確認**:
   ```bash
   sudo netstat -tlnp | grep :8000
   sudo ss -tlnp | grep :8000
   ```

2. **ファイアウォール設定**:
   ```bash
   sudo ufw allow 8000/tcp
   ```

### Bot が Discord に接続できない場合

1. **トークンを確認**:
   ```bash
   sudo -u botcheck cat /opt/botcheck/.env | grep DISCORD_TOKEN
   ```

2. **API との接続を確認**:
   ```bash
   curl http://localhost:8000/health
   ```

## セキュリティ考慮事項

- botcheck ユーザーはシステムログインが無効化されています
- サービスは最小限の権限で実行されます
- `/opt/botcheck/data` と `/opt/botcheck/logs` のみ書き込み可能です
- メモリとCPU使用量に制限が設けられています

## パフォーマンス調整

### API サーバーのワーカー数調整

`/etc/systemd/system/botcheck-api.service` で `--workers` オプションを調整:

```
ExecStart=/opt/botcheck/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 4
```

### リソース制限の調整

サービスファイルの `MemoryMax` と `CPUQuota` を調整してください。

## ログローテーション

systemd ログのローテーション設定:

```bash
# /etc/systemd/journald.conf
SystemMaxUse=100M
SystemKeepFree=50M
SystemMaxFileSize=10M
```