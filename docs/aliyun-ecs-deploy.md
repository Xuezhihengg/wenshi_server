# 阿里云 ECS 生产部署指南

本文档用于把问事后端、Admin 系统、门户网站部署到阿里云 ECS，并通过 `wenshi.xin` 对外提供服务。

## 1. 阿里云控制台准备

### 域名解析

在阿里云 DNS 解析中添加：

| 主机记录 | 类型 | 记录值 |
| --- | --- | --- |
| `@` | A | ECS 公网 IP |
| `www` | A | ECS 公网 IP |

解析生效后本地验证：

```bash
dig +short wenshi.xin
dig +short www.wenshi.xin
```

### 安全组

ECS 安全组入方向至少开放：

| 端口 | 用途 |
| --- | --- |
| `22` | SSH |
| `80` | HTTP / Let's Encrypt 验证 |
| `443` | HTTPS |

不要开放 PostgreSQL `5432`、Redis `6379`、API `8000` 到公网。

## 2. ECS 安装基础软件

以下以 Ubuntu 22.04/24.04 为例：

```bash
sudo apt update
sudo apt install -y ca-certificates curl git ufw

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

重新登录 SSH，让 Docker 用户组生效。

可选防火墙：

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

## 3. 上传代码

推荐目录：

```text
/opt/wenshi/wenshi-server
/opt/wenshi/wenshi-portal
```

如果使用 Git：

```bash
sudo mkdir -p /opt/wenshi
sudo chown -R "$USER":"$USER" /opt/wenshi
cd /opt/wenshi
git clone <你的仓库地址>/wenshi-server.git
git clone <你的仓库地址>/wenshi-portal.git
```

如果暂时不用 Git，可以从本机上传：

```bash
rsync -av --exclude node_modules --exclude .venv --exclude dist \
  /Users/xuezhihengg/Documents/Codes/wenshi-server/ root@ECS_IP:/opt/wenshi/wenshi-server/

rsync -av --exclude node_modules --exclude dist \
  /Users/xuezhihengg/Documents/Codes/wenshi-portal/ root@ECS_IP:/opt/wenshi/wenshi-portal/
```

## 4. 配置生产环境变量

```bash
cd /opt/wenshi/wenshi-server
cp .env.example .env
nano .env
```

必须修改：

```env
ENVIRONMENT=production
POSTGRES_PASSWORD=一个强密码
DATABASE_URL=postgresql+asyncpg://wenshi:同一个强密码@postgres:5432/wenshi
JWT_SECRET=至少32位随机字符串
ADMIN_USERNAME=你的管理员邮箱
ADMIN_PASSWORD=管理员强密码
CORS_ORIGINS=https://wenshi.xin,https://www.wenshi.xin
PUBLIC_BASE_URL=https://wenshi.xin
ADMIN_VITE_API_BASE_URL=/
PORTAL_VITE_API_BASE_URL=/
```

生产验证码建议：

```env
PHONE_VERIFICATION_PROVIDER=dypnsapi_sms
EMAIL_VERIFICATION_PROVIDER=aliyun_dm
```

并填好阿里云短信、DM、AI、Apple 登录等密钥。

## 5. 首次启动 HTTP

```bash
cd /opt/wenshi/wenshi-server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

检查：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl http://wenshi.xin/health
curl http://wenshi.xin/api/v1/memberships/plans
```

访问：

```text
http://wenshi.xin/
http://wenshi.xin/admin/
```

## 6. 签发 HTTPS 证书

确保 `wenshi.xin` 和 `www.wenshi.xin` 都解析到 ECS，且 80 端口可访问。

```bash
cd /opt/wenshi/wenshi-server
CERTBOT_EMAIL=你的邮箱 DOMAIN=wenshi.xin ./infra/scripts/issue_cert.sh
```

脚本会：

1. 使用 webroot 方式申请 `wenshi.xin` 和 `www.wenshi.xin` 证书。
2. 将 Nginx 切换到 HTTPS 配置。
3. 重启 Nginx。

检查：

```bash
curl -I https://wenshi.xin
curl https://wenshi.xin/health
```

## 7. 设置证书自动续期

```bash
crontab -e
```

加入：

```cron
15 4 * * * cd /opt/wenshi/wenshi-server && ./infra/scripts/renew_cert.sh >> /var/log/wenshi-certbot.log 2>&1
```

## 8. 数据库备份

手动备份：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup
```

每日自动备份：

```cron
0 3 * * * cd /opt/wenshi/wenshi-server && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backup >> /var/log/wenshi-backup.log 2>&1
```

## 9. 更新发布

```bash
cd /opt/wenshi/wenshi-server
git pull
cd /opt/wenshi/wenshi-portal
git pull
cd /opt/wenshi/wenshi-server
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

API 容器启动时会自动执行：

```bash
alembic -c apps/api/alembic.ini upgrade head
```

## 10. 常用排障命令

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U wenshi -d wenshi
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli ping
```

如果 Admin 或门户调用接口失败，优先看：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
```
