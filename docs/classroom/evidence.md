# 课堂派截图与提交材料索引

直接上传请使用[按日期与课堂派顺序整理的提交材料](提交材料/README.md)：文件用作业完整名称命名，多张图附内容后缀。

已保存十项作业的[原文与示例说明](requirements.md)、[实现分析](implementation-analysis.md)，并准备下列十张真实运行截图。截图按作业日期分为 `0923`、`0930` 两组，同组内按提交内容编号。课堂派提交和与老师确认补交由学生本人处理。

## 按作业选择材料

| 课堂派作业 | 选用的材料 | 当前准备情况 |
| --- | --- | --- |
| 0923 系统运行截图 | [教师首页](../evidence/classroom/0923/01-teacher-home.jpg) | 教师、班级、列表、正文、上传和下载入口可见 |
| 0923 登录 HTTP | [请求参数](../evidence/classroom/0923/02-login-payload.jpg)、[响应 JSON](../evidence/classroom/0923/03-login-response.jpg)、[完整响应头](../evidence/classroom/0923/04-login-response-headers.jpg) | POST、200、身份字段与八项响应头；认证值已遮盖 |
| 0923 登录后身份识别 | [Cookie 材料请求](../evidence/classroom/0923/05-cookie-direct-api.jpg) + 实现分析的“浏览器如何识别用户” | 地址栏 GET 自动携带 Cookie，返回本班材料；200 可见 |
| 0923 上传逻辑与类型 | 实现分析的“文件上传” | 原要求提交分析，已写支持类型、权限、解析、入库与失败处理 |
| 0923 下载权限与逻辑 | [无有效会话下载 401](../evidence/classroom/0923/06-unauthorized-download.jpg) + 实现分析的“文件下载” | 下载文件接口、401 和错误响应可见；跨班 404 另由测试验证 |
| 0923 后端 API 访问 | 实现分析的“API 暴露与部署” + [直接 API](../evidence/classroom/0923/05-cookie-direct-api.jpg) | 按实际 Flask/Gunicorn、Compose loopback 映射说明，不套用老师 Nginx 示例 |
| 0923 课后任务 | [公开仓库地址](https://github.com/0xkoa1a/CampusClaw) + [第四课变更](../../openspec/changes/archive/2026-09-30-add-traceable-vector-retrieval/proposal.md) | 该项交仓库地址；原有第四课变更已在仓库，本次新增内容仍需另行 push |
| 0930 token 登录 | [Bearer 材料请求](../evidence/classroom/0930/01-bearer-materials.jpg)，可附 0923 组的请求参数与响应 JSON | 真实 Authorization: Bearer 请求与 200；按示例补了 JWT 实现 |
| 0930 知识库 AI 问答 | [AI 回答](../evidence/classroom/0930/02-ai-answer.jpg)、[来源高亮](../evidence/classroom/0930/03-source-highlight.jpg) | 真实课程网关回答、引用材料、可点击的原文来源；不是模拟回答 |
| 0930 课后方案整理 | [方案 PDF](0930/authentication-and-knowledge-qa.pdf)，截止 2026-10-15 00:00；另有 [Markdown](0930/authentication-and-knowledge-qa.md) 和 [HTML](0930/authentication-and-knowledge-qa.html) | 6 页 PDF 已修订并逐页检查；平台提交由学生本人处理 |

补充图 [B 班学生首页](../evidence/classroom/0923/07-student-b-home.jpg) 显示学生无上传入口、列表仅有 B 班材料。此图用于补充角色和班级隔离证据，本身不证明跨班下载状态码。原有第三课交叉验收的三张截图也归入 `0923/peer-verification/`，见[第三课验收记录](../week03-verification.md)。

本次目录整理的[验证截图](../evidence/repository/assignment-screenshot-layout.jpg)保存在 `repository/`，用于仓库整理记录。

0930 课后报告的 [HTML 真实预览](../evidence/classroom/0930/04-report-html-preview.png) 和 [PDF 首页渲染](../evidence/classroom/0930/05-report-pdf-first-page.png) 同样按作业日期归档。这两张图记录文档制作结果；报告的完整交付与验证说明见 [0930 报告目录](0930/README.md)。

老师 AI 示例将切片偏移与摘录直接放在回答下方。本系统将引用做成链接，点击后打开实际原文并高亮；AI 回答与来源高亮应一起使用。token 示例是学生界面，本次 Bearer 图使用教师账号展示同一请求机制；平台正文没有限定账号角色。

## 截图环境与真实性

截图来自当前改动构建的 CLab 独立测试容器，绑定远端 `127.0.0.1:18081`，经 SSH 隧道访问本机同名端口。数据库和上传目录在测试容器内，Qdrant 使用独立集合。既有 `/home/ubuntu/campusclaw-yyx` 正式服务及其 8080 端口未部署此次 Bearer 改动。

使用三个公开的测试账号及与测试代码相同的测试密码，材料仅包含种子样例和 [A 班合成科学材料](fixtures/A班-合成科学材料.md)。教师通过实际上传接口创建材料 ID 3，向量索引状态为 ready。课程网关生成嵌入和回答，问题为“磁铁能吸木块吗？”，实际回答为“不能，磁铁不能吸引木块[1]。”。引用跳转到 ID 3 的真实切片，并高亮正文。

教师首页、AI 回答、来源高亮和 B 班学生首页是独立浏览器中的页面截图；登录载荷、响应、响应头、Cookie、Bearer 和未授权下载图是 Chrome Network 的实际请求截图。桌面图原始尺寸为 3840 × 1908，查看请求字段时请打开原图放大。

登录响应、响应头、Cookie 和 Bearer 图中的测试 JWT/session 在暂存原图前已从测试 sessions 表撤销，并核实有效会话数为 0。随后仅用不透明色块遮盖认证值；接口、状态码、身份字段、Bearer 方案及 Cookie 属性保留。仓库不保存未脱敏原图、课程网关密钥、课堂派凭据或老师示例的认证值。请求参数图的密码是此隔离环境公开测试值，不是个人或正式服务密码。

所有请求记录先完成，再撤销会话、截图和脱敏，因此图中的历史 200 与此后会话失效并不矛盾。未授权下载图直接访问上传文件下载接口时已无有效会话，返回 401。最后一次正常浏览器退出后再次确认 sessions 表为空。

取图完成后，四份临时认证原图已清理，独立测试容器已停止；容器数据保留便于复核。原有正式应用仍报告 healthy，Qdrant 仍运行。

## 验证记录

- `python -m pytest -q`：51 项通过，涵盖原有功能与新增 JWT 签名、期限、issuer/audience、必需 claims、subject 绑定、登出撤销、无 Cookie 请求、非法 Bearer 不回退、角色和跨班拒绝。
- 浏览器完成教师登录、真实 Bearer 材料请求、Cookie 直接 API、无有效会话下载 401、B 班列表、正常退出后材料页重定向登录。
- AI 图使用真实服务；来源图通过实际点击回答中的引用取得。
- 跨班文件下载 404 有自动化测试。本次独立浏览器阻止了错误状态 API 导航，未将其浏览器错误页当作跨班证据截图。
- OpenSpec strict、JavaScript 语法、Git 空白及文件清单在本地提交前核对。平台是否接受补交、是否允许认证值脱敏，以教师答复为准。

## 后续补取方法

先部署到独立验收环境。若使用本地开发服务，可在仓库根目录执行 `python -m scripts.evidence_server --data-dir /absolute/new/temp-directory`，必须使用新目录。脚本生成独立密钥、数据库和随机 Qdrant 集合，仅监听 loopback；有真实网关配置才可能成功取得 AI 回答，缺配置会显示实际失败，不生成假答案。

认证截图要先完成真实请求，撤销截图中的测试会话，再暂存原图到仓库外并脱敏。可用 `scripts/redact_evidence.py`，依赖 Pillow 10.1+；矩形坐标为原图像素的 left,top,right,bottom。检查输出后才放入截图目录和 commit。不能用截图修改接口结果、身份、状态码或回答内容。

每次提交应包含与改动或验证相关的真实截图。local commit、GitHub push 和课堂派提交各自核实；当前留档不声称已完成后两项。
