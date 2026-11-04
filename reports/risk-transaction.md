# 异步批改：事务验证

提交接口在 `BEGIN IMMEDIATE` 中写提交、任务和 outbox，任一写入失败整笔回滚。模型与 RabbitMQ 调用在事务外完成，避免网络等待占用 SQLite 写锁。

| 故障或竞争 | 本地测试观察 |
| --- | --- |
| outbox INSERT 触发异常 | HTTP 503；三张表均无残留 |
| 同键并发提交 | 同正文返回同一任务；不同正文返回 409 |
| 发布消息未确认 | outbox 保持未发布，后续可补投 |
| 旧发布确认晚于新重试 | generation 条件更新不覆盖新一轮 outbox |
| 消费者租约过期 | 任务恢复 pending；旧 token 不能写结果 |
| 结果重复写入 | submission_id、task_id 唯一约束拒绝第二份结果 |
| 暂时失败直到上限 | 指数退避并加抖动；第三次进入 dead，保留原因并排入死信 outbox |
| 永久失败 | 首次进入 failed，不重新调用模型 |

测试入口：`tests/test_async_grading.py`、`tests/test_task_queue.py`、`tests/test_grading.py`。迁移用增量 ALTER/CREATE 保留原作业编号，可重复执行；DDL 事务失败也应回滚。

代理发布与数据库提交不是同一事务。发布成功但 outbox 标记前崩溃会重复投递，靠消费端租约与结果唯一约束收敛。模型调用完成、结果提交前崩溃会重复计费，不能保证只调用一次。

CLab 已验证代理进程重启保留 20 条消息、消费者运行中被终止后第二次尝试成功、已完成任务重复投递不新增结果。21 份提交、任务、结果在应用重建后计数一致，见[唯一性核对](../docs/evidence/classroom/week08/clab-uniqueness.json)和[重建计数](../docs/evidence/classroom/week08/clab-restart.json)。一致性数据库及上传备份位于 `backups/week08-20261104-data/`，没有复制私有配置。本次没有执行物理机器断电测试或覆盖旧第六课数据卷。
