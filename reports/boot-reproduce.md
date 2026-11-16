# 换目录启动与容器验收

CLab 的独立目录 `/home/ubuntu/workspace/campusclaw/verification/week10` 使用 Compose 项目 `campusclaw-week10-20261117`，服务监听 `127.0.0.1:18100`。从 Git 源包展开后，运行 `scripts.prepare_week08_acceptance` 初始化独立配置和新数据卷；该脚本最终执行 `docker compose up --build -d --wait`。镜像更新到 `bd68f97` 后再次完成真实网关批改与安全检查。

| 检查 | 实际结果 |
| --- | --- |
| app、MCP、RabbitMQ | running，健康检查 healthy |
| worker、Qdrant | running；以实际批改、索引和检索检查可用性 |
| 应用就绪 | `/ready` 返回 `status=ready`，检查 SQLite |
| 运行身份 | UID 10001 |
| 运行目录 | `/app` 下项目 `.py` 文件 0 个；无 `.env`，pip 不可导入 |
| 镜像追溯 | app、worker 的 OCI revision 均为 `bd68f97143951041a6960fc627b750deb2dfc809` |
| 迁移与重启 | d57 数据库一致性快照后重建 app、worker；原材料、技能和账号保留，第二次专项验收通过 |

数据库使用 SQLite 命名卷，未执行课程示例中的 MySQL 迁移。Qdrant、MCP、RabbitMQ 均为真实容器；网关调用使用服务器既有配置。第六、八课项目继续独立运行。

迁移阶段为 expand/migrate：增补审计表、索引、通知表和 MCP 耗时字段，不删除旧结构。更新前 SQLite 通过 backup API 保存一致性快照，位置为 `archives/backups/week10/pre-bd68f97.sqlite3`，权限 0600。配置保留在部署原位，未复制私有 `.env`。

原始运行结果见 [clab-runtime.json](week10-local/clab-runtime.json)，真实业务结果见 [clab-security-real.json](week10-local/clab-security-real.json)。后者确认提交 202、RabbitMQ 消费成功、真实网关评分、学生改分 403 和跨班任务 404。截图见[容器记录](../docs/evidence/classroom/week10/06-CLab告警与容器运行记录.png)。启动步骤统一维护在[运行说明](../docs/running.md)。
