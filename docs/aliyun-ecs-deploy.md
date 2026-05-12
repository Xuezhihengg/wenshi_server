# 阿里云 ECS 生产部署指南

本文档用于把问事后端、Admin 系统、门户网站部署到阿里云 ECS，并通过 `wenshi.xin` 对外提供服务。

## 1. 阿里云控制台准备

### ICP 备案

如果 ECS 是中国内地区域，`wenshi.xin` 解析到该 ECS 并对外提供 Web 服务前，通常需要先完成 ICP 备案。未备案域名在中国内地服务器上使用 `80/443` 提供网站服务时，可能无法正常访问或被云厂商拦截。

如果 ECS 是中国香港或海外区域，备案要求不同，但国内访问延迟、短信/邮箱回调、App 审核材料仍需另行评估。

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

你的 ECS 内核 `al8` 属于阿里云 Alibaba Cloud Linux 8 系列，没有 `apt`，使用 `dnf`/`yum`。

### Alibaba Cloud Linux 8 / CentOS 8 系

```bash
sudo dnf makecache
sudo dnf install -y yum-utils ca-certificates curl git tar

sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

docker --version
docker compose version
```

如果 Docker 官方源访问慢，可以改用阿里云源：

```bash
sudo yum-config-manager --add-repo http://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
sudo dnf makecache
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

重新登录 SSH，让 Docker 用户组生效。也可以临时用 `sudo docker ...` 继续操作。

国内 ECS 拉 Docker 官方镜像可能较慢。建议在阿里云控制台进入「容器镜像服务 ACR → 镜像工具 → 镜像加速器」，获取你的专属加速地址，并按控制台提示写入 `/etc/docker/daemon.json`。

### 防火墙

阿里云 ECS 首要看「安全组」是否开放 `80/443`。系统内防火墙如果启用了 `firewalld`，再执行：

```bash
sudo firewall-cmd --state || true
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

如果 `firewall-cmd` 提示未安装或未运行，通常只配置阿里云安全组即可。

### Ubuntu 备选

如果以后换成 Ubuntu 22.04/24.04，再使用 `apt` 安装 Docker。当前这台 AL8 不需要执行 Ubuntu 命令。

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
