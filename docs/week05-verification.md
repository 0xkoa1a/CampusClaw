# 第五课实现与验收

## 已完成的必要测试

2026-10-14 在本地与 CLab 独立验收环境执行。业务包含技能文件、教师智能体配置与绑定、用户私有会话、历史窗口、真实 SSE、同源 Swagger 和逐接口测试。第四课 search/ask 与原认证保持兼容。

| 验证 | 结果 |
| --- | --- |
| 本地 pytest | 117 项通过，包含原有 65 项回归 |
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

教师编辑、学生提问、历史恢复、来源跳转、移动布局与 Swagger Bearer 试调已逐项操作。完整浏览器脚本在重复及并行验收中发现初始化与新建会话的状态竞态，后续修复并重新全流程确认；退出时自动身份检查可能收到预期 401，需与页面错误分别记录。

## 部署状态与剩余验收

隔离环境绑定远端 loopback 18083，数据库、上传目录和 Qdrant 集合独立。正式应用尚待部署。部署前备份已完成：`/home/ubuntu/campusclaw-backups/week05-20261014-before`，包含旧镜像引用、私有环境配置、源码、SQLite 一致快照及上传文件。原数据为 3 个账号、2 个班、4 份材料、4 个切片、2 个上传文件。

后续完成正式部署与重启数据核对，再由真实同学使用独立账号验证会话归属、智能体隔离、班级边界和技能开关。未取得第二方证据，OpenSpec 保持活跃。

## 复现入口

- 规约与任务：`openspec/changes/add-agent-skill-streaming-conversations/`。
- 本地回归：`python -m pytest -q`。
- 独立截图环境：`python -m scripts.week05_evidence_server --data-dir /absolute/new/directory`，默认使用真实网关；显式 `--stub-model` 仅用于本地确定性页面测试。
- 真实流核对：`python -m scripts.verify_week05 --base-url http://127.0.0.1:18083`，只允许公开测试环境，逐字核对合成材料后才发送模型请求。
- 接口验收：见 [apitest 使用说明](../apitest/README.md)。HTML 报告在忽略目录，提交代码和证据截图。
- 私有部署备份：`scripts/backup_deployment.py` 在 CLab 上运行，备份目录必须为部署目录外的新目录。
