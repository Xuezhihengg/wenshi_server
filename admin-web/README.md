# Wenshi Admin

问事管理后台，React + Vite 单页应用，构建后由 nginx 提供 `/admin/`。

```bash
npm install
npm run dev
```

开发环境默认访问 http://127.0.0.1:5173，API 地址由 `VITE_API_BASE_URL` 控制，默认 `http://localhost:8000`。

```bash
npm run typecheck
npm run build
```

生产构建由 `docker-compose.yml` 的 `admin-web` 服务完成，`VITE_BASE_PATH=/admin/`。
