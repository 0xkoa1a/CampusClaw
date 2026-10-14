# 第五课实现与验收

## 已完成的必要测试

2026-10-14 在本地与 CLab 独立验收环境执行。业务包含技能文件、教师智能体配置与绑定、用户私有会话、历史窗口、真实 SSE、同源 Swagger 和逐接口测试。第四课 search/ask 与原认证保持兼容。

| 验证 | 结果 |
| --- | --- |
| 本地 pytest | 118 项通过，包含原有 65 项回归；其中一项运行 4 个 Node 认证脚本测试 |
| OpenSpec strict | 活跃第五课变更及三份正式规格通过 |
| CLab 真实 HTTP + SQLite 验收 | apitest 13 个脚本全部通过 |
| 真实网关有资料回答 | 7 个下游 delta，含服务端补充的来源编号；正文与数据库一致 |
| 真实网关无资料回答 | 117 个 delta，引用为空且不含编号；正文与数据库一致 |
| JavaScript/Python 语法、Git 空白 | 通过 |

真实网关生成“检查常数项的符号。”，未直接给出 x 的值；原文包含相应检查规则。模型未写编号时，服务端另附“参考资料：[1]”。无资料分支给出一般学习建议。网关有批量到达的片段，不把下游分帧数当作模型 token 数或匀速输出证明。完整时间记录与合成回答见[流式验证 JSON](evidence/classroom/week05/07-stream-verification.json)。

## 运行截图

截图来自 CLab 隔离服务，经本机 SSH 隧道访问，使用公开测试账号及合成数学、语文材料。未使用正式用户资料。原始页面截图不包含 API Key、JWT 或 Cookie。

- [教师配置](evidence/classroom/week05/01-teacher-config.png)
- [学生解题引导与引用](evidence/classroom/week05/02-student-answer.png)
- [多轮对话](evidence/classroom/week05/03-multi-turn.png)
- [原文高亮](evidence/classroom/week05/04-source.png)
- [移动端](evidence/classroom/week05/05-mobile.png)
- [Swagger](evidence/classroom/week05/06-swagger.png)
- [初始化期间禁用操作](evidence/classroom/week05/08-initialization-guard.png)
- [新建期间防止重复提交](evidence/classroom/week05/09-creation-guard.png)

已修复页面初始化与新建会话重叠、重复新建请求，以及退出时后台请求引发重复跳转的问题。新建期间禁用提问、切换和删除会话；退出时取消初始身份检查，并忽略尚未完成的后台响应。

修复后使用 Playwright Chromium 在 `http://127.0.0.1:19084` 验证教师编辑、学生真实流式提问、刷新恢复、多轮对话、来源跳转、Swagger Bearer 试调与退出。桌面视口为 1440×1000，手机视口为 390×844，页面无横向溢出，未发现 JavaScript 错误。当前环境未提供 Browser 技能，使用已有 Playwright 安装。

另用受控网络延迟验证初始化和新建期间的按钮状态，并重复触发表单提交：只产生一个新建请求。两张操作保护截图来自该测试。退出流程记录到一次 `/api/materials` 的 401，登录页正常打开，没有重复跳转或导航中断。4 个 Node 测试覆盖身份检查取消、后台 401、退出失败后重试及普通 401 的令牌清理。

## 部署状态与剩余验收

隔离环境绑定远端 loopback 18083，本次页面修复另在 18084 验证；数据库、上传目录和 Qdrant 集合独立。正式应用尚待部署。部署前备份已完成：`/home/ubuntu/campusclaw-backups/week05-20261014-before`，包含旧镜像引用、私有环境配置、源码、SQLite 一致快照及上传文件。原数据为 3 个账号、2 个班、4 份材料、4 个切片、2 个上传文件。

后续完成正式部署与重启数据核对，再由真实同学使用独立账号验证会话归属、智能体隔离、班级边界和技能开关。未取得第二方证据，OpenSpec 保持活跃。

## 复现入口

- 规约与任务：`openspec/changes/add-agent-skill-streaming-conversations/`。
- 本地回归：`python -m pytest -q`。
- 独立截图环境：`python -m scripts.week05_evidence_server --data-dir /absolute/new/directory`，默认使用真实网关；显式 `--stub-model` 仅用于本地确定性页面测试。
- 真实流核对：`python -m scripts.verify_week05 --base-url http://127.0.0.1:18083`，只允许公开测试环境，逐字核对合成材料后才发送模型请求。
- 接口验收：见 [apitest 使用说明](../apitest/README.md)。HTML 报告在忽略目录，提交代码和证据截图。
- 私有部署备份：`scripts/backup_deployment.py` 在 CLab 上运行，备份目录必须为部署目录外的新目录。
