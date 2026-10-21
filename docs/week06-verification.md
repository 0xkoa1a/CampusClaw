# 第六课实现与验证

## 要求与计划

Luna 从[课程网站](https://devops.hello1023.com/)确认最新可用材料为第六课《MCP 与工具接入》，后续课件尚未提供。逐页提取和 11 份原始 HTML 已保存在[课程参考目录](course/week06/README.md)，其中区分任务清单、教程口径、建议与页面内部表述差异。

实施采用 [OpenSpec 计划](../openspec/changes/add-platform-tools-and-call-traces/tasks.md)：同仓 HTTP MCP 服务 → 服务器登记与发现 → 技能引用和模型工具调用循环 → 实际调用记录与页面 → 真实网关验证 → PDF。主智能体负责规约、权限、调用链与结果复核，Luna 完成网页归档、独立 MCP 服务、登记与管理页面、测试脚本和提交索引。

## 实现结果

- `mcp-server/` 提供 `/health` 与 Bearer 鉴权的 `POST /mcp`，实现 initialize、tools/list、tools/call，包含 calculate 和 unit_convert 两个只读工具；Compose 与主应用一并构建启动，MCP 端口仅在内部网络使用。
- 教师登记本班服务器，令牌从服务端指定环境变量读取，登记响应只返回配置状态。地址使用管理员允许列表，拒绝重定向，发现参数结构拒绝远程引用。
- 技能保存时校验 `工具名@服务器名`；每轮再次检查连接和班级。调用失败返回失败数据，断开后清缓存并标为 denied。模型工具循环最多两轮、累计四次执行，并检查时间预算。
- 提供三个内置应用的安装入口、提示词模板、技能样板与文件导入。重复安装保留教师已有的同名配置。
- 真实模型请求与返回按会话所有者授权查看，教师另可查看本班工具审计。调用记录不包含 HTTP 认证头；只有合成环境证据进入 Git。

## 验证

2026-10-21 在 CLab 新建独立 Compose 项目 `campusclaw-week06-20261021`，源码目录 `/home/ubuntu/campusclaw-week06-iJHZCm`，主应用绑定远端 loopback 18086，经本机 19086 隧道访问。独立数据卷保存合成资料，不替换旧部署目录。重建后合成材料、会话和审计仍可读取。

| 检查 | 结果 |
| --- | --- |
| Python 回归与新增测试 | 177 项通过，包含此前 118 项基线 |
| OpenSpec strict | 2 个活跃变更与 3 份正式规格全部通过 |
| MCP HTTP 鉴权 | 无令牌 401；错误令牌 401；正确令牌 200，发现两个工具 |
| 普通与知识问答 | 真实 SSE 完成；命中技能正文进入 system，未命中技能与未绑定资料未发送 |
| 真实模型选择 calculate | add、23.0、19.0；MCP 文本 42.0；最终回答 42，审计 ok |
| 真实模型选择 unit_convert | 150.0、cm、m；MCP 文本 150.0 cm = 1.5 m，审计 ok |
| 断开服务器 | 无新的远端调用，meta 和审计为 denied，最终回答正常结束 |
| 长文档范围 | 8 个章节只返回 4 个切片，进入请求的章节标记为 5 个，完整正文未发送 |
| 数据库正文 | 5 个主要场景的最终记录与 SQLite 消息逐字一致 |
| Swagger MCP 试调 | 浏览器 Bearer 授权后 GET /api/mcp/servers 返回 200 |
| JavaScript、空白、提交材料索引 | 语法、Git diff 和索引检查通过 |
| 交付文件凭据检查 | 与隔离环境真实 SECRET_KEY、MCP_AUTH_TOKEN、网关密钥逐项比对，未发现泄漏 |

工具规划请求使用 stream=false，最终回答使用 stream=true。计算和换算场景分别产生两次规划请求、一次最终流式请求。服务端记录的是实际发送参数与网关返回；不把客户端 max_tokens 当作网关实际执行上限，也不把下游 delta 数当作模型 token 数。

## 页面与报告

使用 frontend-testing-debugging 技能。当前没有 Browser 技能，使用已有 Playwright Chromium。桌面 1440×1000、手机 390×844：页面身份与正文正常，无框架错误遮罩，无页面 JavaScript 错误，无横向溢出。

已实际操作：教师连接与发现、审计刷新、安装内置应用、选择提示词模板和内置技能、导入并保存技能文件；学生查看工具回答、读取自己的模型调用记录、刷新恢复与退出。另在手机宽度检查了展开的调用记录，无横向溢出。页面截图均来自真实隔离服务。

报告按 clear-writing 整理，使用 `vuepress-notes-template` 的临时副本导出自包含 HTML，再以 Chromium 打印为 5 页 A4 PDF。HTML 在桌面与手机宽度下无溢出、无外部请求和运行错误；PDF 已逐页渲染检查。模板原仓库已有的三处用户修改保持不变。

## 提交入口与复现

[提交材料索引](classroom/提交材料/README.md#week06)集中链接 Markdown、HTML、PDF、7 张截图和两份 JSON，文件都在 `docs/classroom/提交材料/week06/`。日期尚未由课堂派确认，目录使用课号。

- 首次启动与教师配置：[运行说明](running.md#mcp-与应用配置)。
- 核心真实验证：`python -m scripts.verify_week06 --base-url http://127.0.0.1:19086 --output /private/tmp/week06.json`，要求全新合成测试环境。
- 补充范围验证：`python -m scripts.verify_week06_rag_scope --base-url http://127.0.0.1:19086 --output /private/tmp/week06-rag.json`。
- 回归：`python -m pytest -q`；文档：`openspec validate --all --strict`。
- 提交索引：`python scripts/prepare_classroom_submission.py --check`。

当前变更保持活跃，等待用户后续提供阶段验收清单再逐项对账。课堂派提交由用户本人完成。
