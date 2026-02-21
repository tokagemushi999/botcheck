# top.gg Registration Information for BotCheck

## Bot Information

### Basic Details
- **Bot Name**: BotCheck
- **Bot ID**: `1474728574320640011`
- **Prefix**: `/` (slash commands only)
- **Website**: https://botcheck-production-db00.up.railway.app
- **GitHub**: https://github.com/tokagemushi999/botcheck
- **Support Server**: https://discord.gg/YOUR_INVITE_CODE_HERE (要更新)

### Short Description (150文字以内)
Discord server AI/bot detection with 4-engine analysis. Real-time monitoring, detailed scoring, and automated alerts for suspicious accounts.

### Long Description (最大5000文字)
BotCheck is an advanced Discord bot detection system that uses four independent analysis engines to identify suspicious AI/bot accounts in your Discord server.

**Key Features:**
- **4-Engine Analysis**: Timing, Style, Behavior, and AI Detection engines work together to provide accurate bot detection
- **Real-time Monitoring**: Automatically analyzes all messages and maintains user profiles
- **Detailed Scoring**: Provides comprehensive 0-100 scores with confidence ratings
- **Automated Alerts**: Notifies administrators when suspicious accounts exceed thresholds
- **Web Dashboard**: View server statistics, score distributions, and suspicious user rankings
- **Privacy First**: All data is stored securely and only accessible by server administrators

**How It Works:**
1. **Timing Analysis**: Detects robotic posting patterns, unnatural response speeds, and suspicious activity schedules
2. **Style Analysis**: Identifies AI-generated text through vocabulary diversity, sentence structure, and punctuation patterns  
3. **Behavior Analysis**: Examines channel usage, reply patterns, and social interaction behaviors
4. **AI Detection**: Recognizes AI-specific traits like excessive formality, template responses, and unnatural consistency

**Commands:**
- `/botcheck user [member]` - Analyze a specific user's bot probability
- `/botcheck server` - View server-wide statistics and suspicious users
- `/botcheck scan` - Import historical messages from current channel
- `/botcheck watch` - Toggle real-time monitoring on/off
- `/botcheck report` - Generate weekly bot detection report

**Perfect for:**
- Gaming communities fighting bot invasions
- NFT/crypto servers preventing spam bots
- Large communities maintaining authentic engagement
- Moderation teams needing automated assistance

Open source, privacy-focused, and continuously improving through community feedback.

### Tags
bot-detection, moderation, security, analysis, ai-detection, anti-spam, server-management, automation

### Category
- Primary: Moderation
- Secondary: Utility

### Bot Permissions Required
- Send Messages
- Use Slash Commands
- Read Message History
- View Channels
- Add Reactions
- Manage Messages (for alerts)

### Webhook Configuration
- **Webhook URL**: `https://botcheck-production-db00.up.railway.app/webhook/topgg`
- **Authorization Header**: (none currently - can be added later with API token)

### Vote Rewards
Users who vote on top.gg receive 24 hours of Pro features:
- Unlimited analyses
- Detailed 4-engine scores
- Extended scan limits (1000 messages)
- Weekly reports access

## Screenshots Needed

1. **Main Interface**: Screenshot of `/botcheck user` analysis results
2. **Server Overview**: Screenshot of `/botcheck server` command output
3. **Web Dashboard**: Screenshot of the dashboard showing statistics
4. **Detection Example**: Screenshot showing a high-scoring suspicious user
5. **Settings Panel**: Screenshot of `/botcheck watch` configuration

## Bot Invite Link
```
https://discord.com/oauth2/authorize?client_id=1474728574320640011&permissions=2147559424&scope=bot+applications.commands
```

## Additional Notes for top.gg Staff

### Privacy & Data Handling
- Only stores message metadata (length, timing, etc.) not content for most analyses
- Message content temporarily processed for AI detection but not stored
- All data scoped to individual servers
- Users can request data deletion through support server

### Unique Value Proposition
Unlike simple bot detection tools, BotCheck uses multiple specialized engines to reduce false positives and provide detailed insights. The combination of timing analysis, writing style detection, behavioral patterns, and AI-specific markers creates a robust detection system suitable for communities of all sizes.

### Technical Architecture
- Python 3.11 with discord.py
- FastAPI for web interface and API
- SQLite for data storage
- Deployed on Railway with auto-deployment
- Open source for transparency and community contributions

### Monetization (Future)
- Freemium model with Pro subscriptions
- top.gg voting rewards (24h Pro access)
- API access for Pro users
- No ads or data selling

## Support Information
- **Documentation**: Available at website
- **Issues**: GitHub repository
- **Support Server**: Discord server (link TBD)
- **Contact**: GitHub issues or support server

---

**Note**: Update the support server invite link before submitting to top.gg