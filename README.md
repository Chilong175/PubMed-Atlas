# PubMed 文献检索与可视化 Demo

这是一个用于面试演示的 Python + Docker 网页 Demo，目标是实现 PubMed 文献检索、统计分析、可视化、影响力排序和中文 AI 综述。

## 当前进度

- 第 1 步：项目骨架、FastAPI 服务、Docker 启动配置、首页和健康检查接口。

## 本地启动

1. 复制环境变量文件：

```bash
copy .env.example .env
```

2. 在 `.env` 中填写 `PUBMED_API_KEY`。

3. 启动服务：

```bash
docker compose up --build
```

4. 打开页面：

```text
http://localhost:8000
```

健康检查接口：

```text
http://localhost:8000/health
```

