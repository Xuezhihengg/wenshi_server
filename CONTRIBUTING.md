# Contributing

感谢你愿意参与问事。本文档说明本地开发、提交与评审的基本约定。

## 开发环境

1. 安装 Python 3.11+、[uv](https://docs.astral.sh/uv/)、PostgreSQL 16+、Redis 7+ 与 Node.js 20+。
2. 复制 `.env.example` 为 `.env`，按需修改。
3. 同步依赖并启动服务：

```bash
uv sync --extra dev
uv run alembic -c apps/api/alembic.ini upgrade head
uv run uvicorn app.main:app --app-dir apps/api --reload
```

4. 管理后台：

```bash
cd admin-web
npm install
npm run dev
```

## 提交前检查

```bash
uv run ruff check .
uv run pytest -q
```

新增数据库字段时，请同时提交 Alembic 迁移，并确保 `upgrade head` 可以从空库执行。

## Pull Request

- 一个 PR 只解决一个问题，避免混入无关重构。
- 描述中说明动机、实现方式和验证步骤。
- 新增接口或配置项时同步更新 README 与 `.env.example`。
- 不要提交 `.env`、密钥、证书、生产日志、用户数据或数据库备份。
- 不要提交 `data/uploads/`、`data/logs/` 下的真实内容。

## 提交信息

建议使用清晰的祈使句，例如：

```text
Add membership quota endpoint
Fix avatar URL when behind a proxy
```

## 安全问题

不要在公开 Issue 中披露漏洞。请按 [SECURITY.md](SECURITY.md) 私下报告。
