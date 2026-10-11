# CampusClaw

CampusClaw 集中管理班级教学材料，让教师上传资料、学生查阅资料，并通过知识库检索和简短问答找到原文出处。教师和学生只访问本班材料，权限由服务端判定。

当前支持 `.txt` / `.md` 上传、原文件下载、Cookie 与 Bearer 登录、关键词／向量／混合检索，以及带引用的 AI 问答。Flask 提供页面和 API，SQLite 保存身份、材料与切片，Qdrant 保存向量；课程网关负责嵌入和对话模型调用。

## 启动

需要 Python 3.10+、Docker Engine 和 Compose v2。在仓库根目录执行：

```sh
python3 scripts/setup_env.py
# 在生成的私有 .env 中填写 EMBEDDING_API_KEY
docker compose up --build -d --wait
docker compose exec -T app python -m scripts.reindex_all
```

浏览器打开 <http://localhost:8080/login>，使用 `.env` 中配置的演示账号密码。[运行说明](docs/running.md)包含完整配置、CLab 访问、持久化验收、开发测试和 API 参数。

## 提交与查阅

- [课堂派提交材料](docs/classroom/提交材料/README.md)：按作业日期、平台顺序和完整作业名组织；文字、截图、PDF 都在对应日期目录。
- [课程与课堂派要求](docs/classroom/requirements.md)：课程要求、作业原文、示例说明与截止时间。
- [方案报告源文件与导出记录](docs/classroom/0930/README.md)：Markdown、HTML、PDF 和打印样式。
- [截图采集记录](docs/classroom/evidence.md)：截图环境、认证值脱敏和验证记录。
- [第三课验收](docs/week03-verification.md)、[第四课验收](docs/week04-verification.md)：各阶段的实际验证结果。

## 规约与目录

正式规格：[身份、权限与上传](openspec/specs/auth-upload/spec.md)、[可追溯检索](openspec/specs/traceable-retrieval/spec.md)、[Bearer 认证](openspec/specs/bearer-auth/spec.md)。历史提案、Review 和实施记录保存在 `openspec/changes/archive/`。

| 目录 | 内容 |
| --- | --- |
| `app/` | 服务端、页面模板与浏览器脚本 |
| `scripts/`、`tests/` | 初始化、验收、提交材料同步脚本及自动化测试 |
| `openspec/` | 正式规格与历史变更 |
| `docs/classroom/提交材料/` | 课堂派上传文件和可复制的文字答案 |
| `docs/classroom/0930/` | 方案报告源文件及导出产物 |
| `docs/evidence/` | 运行截图原件与仓库验证截图 |

本学期范围不含家长端、多校区运营和学科交易市场。当前完成第三、四课；第五课暂缓，智能体、业务技能、MCP 和互联网部署按[学期项目要求](docs/classroom/requirements.md#学期项目交付)继续规划。
