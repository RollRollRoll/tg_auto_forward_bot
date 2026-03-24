# Telegram X Video Forward Bot

A Telegram Bot that receives X (Twitter) video links, downloads videos with yt-dlp, and publishes them to Telegram Channels with custom captions.

## Features

- Private chat interaction with authorized admins
- HTML-formatted captions (bold, italic, links, code)
- Multi-channel support with inline keyboard selection
- Configurable video quality and concurrent download limits
- Local Bot API Server for uploads up to 2000 MB
- SQLite database for configuration

## Quick Start (Docker)

1. Get a bot token from [@BotFather](https://t.me/BotFather)
2. Get API credentials from [my.telegram.org](https://my.telegram.org)
3. **Important:** Log out from official API first:
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/logOut
   ```
   Wait 10 minutes before proceeding.
4. Configure:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```
5. Run:
   ```bash
   docker compose up -d
   ```

## Quick Start (Direct)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — ensure Local Bot API Server is running separately
python -m bot.main
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and help |
| `/help` | Show help |
| `/add_channel <chat_id>` | Add target channel |
| `/list_channels` | List channels |
| `/settings` | View all settings |
| `/set <key> <value>` | Update setting |

See `/help` in the bot for full command list.

## 远程服务器部署方案

### 一、申请 Telegram 凭据

#### 1. 获取 Bot Token
1. 在 Telegram 搜索 `@BotFather`，发送 `/newbot`
2. 按提示输入 bot 名称和用户名
3. 记录返回的 Bot Token（格式如 `123456:ABC-DEF...`）

#### 2. 获取 API_ID 和 API_HASH
1. 访问 [my.telegram.org](https://my.telegram.org)
2. 用手机号登录，点击 "API development tools"
3. 创建应用，记录 `api_id` 和 `api_hash`

#### 3. 获取 SUPER_ADMIN_ID
在 Telegram 搜索 `@userinfobot`，发送任意消息，记录返回的数字 ID。

#### 4. 登出官方 API
首次使用 Local Bot API Server 前，需先登出官方 API，**等待 10 分钟**再继续：
```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/logOut
```

### 二、本地打包镜像

```bash
# 在项目根目录构建镜像（指定 linux/amd64 平台以适配大多数云服务器）
docker build --platform linux/amd64 -t tg-auto-forward-bot:latest .

# 导出为 tar 文件
docker save tg-auto-forward-bot:latest -o tg-auto-forward-bot.tar
```

### 三、远程服务器环境准备

```bash
# SSH 登录服务器
ssh user@your-server-ip

# 安装 Docker（Ubuntu/Debian）
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin

# 启动并设置开机自启
sudo systemctl enable docker
sudo systemctl start docker

# 创建项目目录
mkdir -p ~/tg-bot
```

### 四、上传文件到服务器

```bash
# 在本地执行
scp tg-auto-forward-bot.tar user@your-server-ip:~/tg-bot/
scp docker-compose.yml user@your-server-ip:~/tg-bot/
scp .env.example user@your-server-ip:~/tg-bot/.env
```

### 五、服务器上部署

```bash
ssh user@your-server-ip
cd ~/tg-bot

# 导入镜像
docker load -i tg-auto-forward-bot.tar

# 编辑 .env 文件，填入真实凭据
nano .env
```

`.env` 内容：
```
BOT_TOKEN=你的bot_token
API_BASE_URL=http://telegram-bot-api:8081
SUPER_ADMIN_ID=你的telegram_user_id
API_ID=你的api_id
API_HASH=你的api_hash
```

修改 `docker-compose.yml`，将 bot 服务的 `build: .` 改为使用本地镜像：
```yaml
bot:
  image: tg-auto-forward-bot:latest   # 原来是 build: .
```

启动服务：
```bash
docker compose up -d
```

### 六、验证与运维

```bash
# 查看容器运行状态
docker compose ps

# 查看实时日志
docker compose logs -f bot

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新镜像后重新部署
docker load -i tg-auto-forward-bot-new.tar
docker compose up -d
```

在 Telegram 找到你的 bot，发送 `/start`，确认正常响应。

### 备选：直接在服务器上构建

如果不想本地打包，可以上传整个项目到服务器直接构建：

```bash
# 本地上传项目（排除无关目录）
rsync -avz --exclude='venv' --exclude='.git' --exclude='__pycache__' \
  ./ user@your-server-ip:~/tg-bot/

# 服务器上
cd ~/tg-bot
cp .env.example .env
nano .env  # 填写凭据
docker compose up -d --build
```
