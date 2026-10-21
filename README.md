# CampusClaw

CampusClaw 集中管理班级教学材料，让教师上传资料、学生查阅资料，并通过知识库检索和简短问答找到原文出处。教师和学生只访问本班材料，权限由服务端判定。

当前支持 `.txt` / `.md` 上传、原文件下载、Cookie 与 Bearer 登录、混合检索、多个 AI 应用、提示词模板、技能导入、多轮流式回答，以及 HTTP MCP 工具发现与调用。Flask 提供页面和 API，SQLite 保存身份、材料、会话与调用记录，Qdrant 保存向量；课程网关负责嵌入和对话模型调用。

## 启动

需要 Python 3.10+、Docker Engine 和 Compose v2。在仓库根目录执行：

```sh
python3 scripts/setup_env.py
# 在生成的私有 .env 中填写 EMBEDDING_API_KEY；MCP_AUTH_TOKEN 已随机生成
docker compose up --build -d --wait
docker compose exec -T app python -m scripts.reindex_all
```

浏览器打开 <http://localhost:8080/login>，使用 `.env` 中配置的演示账号密码。[运行说明](docs/running.md)包含完整配置、CLab 访问、持久化验收、开发测试和 API 参数。

教师进入 `/conversations`，点击“安装内置应用与技能”即可创建三个应用，再绑定本班资料。进入 `/mcp` 登记 `campus-tools`，Base URL 为 `http://mcp-demo:8090`，令牌环境变量为 `MCP_AUTH_TOKEN`，连接后可在技能中引用 `calculate@campus-tools` 和 `unit_convert@campus-tools`。已有 `.env` 升级前需补充独立随机的 `MCP_AUTH_TOKEN`。

## 提交与查阅

- [课堂派提交材料](docs/classroom/提交材料/README.md)：按作业日期、平台顺序和完整作业名组织；文字、截图、PDF 都在对应日期目录。
- [课程与课堂派要求](docs/classroom/requirements.md)：课程要求、作业原文、示例说明与截止时间。
- [第 5 课参考材料](docs/course/week05/README.md)：在线文档快照、详细功能要求、实践与验收清单。
- [第 6 课参考材料](docs/course/week06/README.md)：HTTP MCP、技能工具引用、调用循环与审计要求。
- [第 6 课实现与验证](docs/week06-verification.md)：实现计划、真实网关证据、页面验证和 PDF 入口。
- [方案报告源文件与导出记录](docs/classroom/0930/README.md)：Markdown、HTML、PDF 和打印样式。
- [截图采集记录](docs/classroom/evidence.md)：截图环境、认证值脱敏和验证记录。
- [第三课验收](docs/week03-verification.md)、[第四课验收](docs/week04-verification.md)：各阶段的实际验证结果。
- [第五课实现与验收](docs/week05-verification.md)：智能体、技能、多轮流式、Swagger 和接口测试；解题助手入口为 `/conversations`。

## 规约与目录

正式规格：[身份、权限与上传](openspec/specs/auth-upload/spec.md)、[可追溯检索](openspec/specs/traceable-retrieval/spec.md)、[Bearer 认证](openspec/specs/bearer-auth/spec.md)。历史提案、Review 和实施记录保存在 `openspec/changes/archive/`。

| 目录 | 内容 |
| --- | --- |
| `app/` | 服务端、页面模板与浏览器脚本 |
| `mcp-server/` | 独立 HTTP MCP 服务，提供计算和单位换算 |
| `scripts/`、`tests/` | 初始化、验收、提交材料同步脚本及自动化测试 |
| `openspec/` | 正式规格与历史变更 |
| `docs/course/` | 课程文档快照与后续实现要求 |
| `docs/classroom/提交材料/` | 课堂派上传文件和可复制的文字答案 |
| `docs/classroom/0930/` | 方案报告源文件及导出产物 |
| `docs/evidence/` | 运行截图原件与仓库验证截图 |

本学期范围不含家长端、多校区运营和学科交易市场。各课的实际测试和部署状态见验证记录；互联网发布继续按[学期项目要求](docs/classroom/requirements.md#学期项目交付)推进。
