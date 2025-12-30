# KKPay 钱包系统 - Webhook 配置指南

## 🚀 快速启动

### 1. 配置环境变量

创建 `.env` 文件：

```env
# Telegram Bot
BOT_TOKEN=your_telegram_bot_token

# KKPay 商户配置
KKPAY_MERCHANT_ID=your_merchant_id
KKPAY_SECRET=your_secret_key

# Webhook 服务器
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
```

### 2. 启动系统

**终端1 - 启动机器人:**
```bash
python3 main.py
```

**终端2 - 启动Webhook服务器:**
```bash
python3 webhook_server.py
```

## 🌐 配置 Webhook 公网访问

### 方案1: 使用 ngrok (推荐用于测试)

```bash
# 安装 ngrok
npm install -g ngrok
# 或下载: https://ngrok.com/download

# 启动 ngrok 隧道
ngrok http 8080
```

ngrok 会显示类似输出：
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8080
```

**在 KKPay 商户后台配置回调地址:**
```
https://abc123.ngrok.io/kkpay/callback
```

### 方案2: 使用 Cloudflare Tunnel (免费，稳定)

```bash
# 安装 cloudflared
# macOS: brew install cloudflared
# 其他系统: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/

# 启动隧道
cloudflared tunnel --url http://localhost:8080
```

获得形如 `https://xyz.trycloudflare.com` 的URL

**在 KKPay 商户后台配置回调地址:**
```
https://xyz.trycloudflare.com/kkpay/callback
```

### 方案3: 部署到云服务器 (生产环境)

#### 使用 VPS/云服务器:

1. **上传代码到服务器**
2. **安装依赖:** `pip install -r requirements.txt`
3. **配置 .env 文件**
4. **启动服务:**
   ```bash
   # 使用 screen 或 tmux 保持后台运行
   screen -S kkpay-bot
   python3 main.py &
   python3 webhook_server.py &
   ```

5. **配置防火墙开放8080端口**
6. **在 KKPay 配置回调地址:** `https://your-domain.com/kkpay/callback`

## 🔧 验证 Webhook 配置

### 检查服务器状态:
```bash
# 本地测试
curl http://localhost:8080/health

# 公网测试 (替换为你的实际URL)
curl https://abc123.ngrok.io/health
```

### 成功响应:
```json
{"status": "healthy", "service": "KKPay Webhook Server"}
```

## 📋 重要注意事项

1. **KKPay要求HTTPS**: 必须使用 HTTPS 回调地址
2. **保持服务运行**: Webhook 服务器必须24/7运行以接收通知
3. **测试回调**: 先用少量金额测试充值/提现流程
4. **日志监控**: 查看 webhook_server.py 的日志输出确认收到回调

## 🔄 工作流程

1. **用户发起充值/提现** → 机器人创建订单
2. **KKPay处理订单** → 向您的 webhook 发送通知
3. **Webhook接收通知** → 更新用户余额
4. **自动发送Telegram通知** → 告知用户操作结果

## 🎯 生产部署建议

- **使用反向代理**: Nginx + uWSGI/Gunicorn
- **SSL证书**: Let's Encrypt 免费证书
- **进程管理**: systemd 或 supervisord
- **数据库**: 替换内存存储为 PostgreSQL/MySQL
