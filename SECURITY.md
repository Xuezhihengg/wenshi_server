# Security Policy

## 支持的版本

安全修复默认应用到 `main` 分支的最新版本。

## 报告漏洞

请不要在公开 Issue、Discussion 或 PR 中披露安全问题。请通过以下方式私下联系维护者：

- 邮箱：`xuezhihengg@gmail.com`

报告时请尽量包含：

- 受影响的版本或提交
- 复现步骤
- 影响范围
- 你认为可行的修复方向

我们会在确认问题后尽快回复，并在修复发布后致谢（如果你愿意公开署名）。

## 敏感信息

仓库中不应出现以下内容：

- `.env` 或任何真实 API Key、AccessKey、JWT Secret
- APNs / FCM / Apple / Google 私钥或证书
- Android keystore、iOS provisioning profile
- 生产数据库导出、用户上传文件、真实日志
- 服务器 IP、SSH 凭据、内部管理地址

如果发现敏感信息被提交，请立即私下报告，维护者会轮换凭据并清理历史。
