# 异步批改：并发验证

## 本地结果

`.venv/bin/python -m scripts.verify_async_local --data-dir <本地隔离目录> --output reports/async-local.json` 对真实本机 HTTP 服务连续提交 20 次，均返回 `202`，响应体不含评分。P95 为 0.0038 秒，测试批改器固定等待 2 秒。消费者暂停时任务保持 pending，恢复后第一条任务成功；同一幂等键重提返回原任务。原始采样见 [async-local.json](async-local.json)。

应用级并发测试 `test_concurrent_same_key_creates_one_submission_task_and_outbox` 用 8 个线程重复提交 16 次，断言只有一份提交、一条任务和一条 outbox。重复投递测试断言已完成任务不再调用批改器，结果表唯一约束阻止第二份结果。

本地传输是内存替身，批改器为确定性替身。该结果验证接收接口不等待批改及应用幂等，不验证代理持久化。

## CLab 实测

- `docker compose stop worker` 后，20 次 HTTP 提交 P95 为 7.24 ms，全为 202、pending，不含评分。
- 用应用的 outbox 投递器发布 20 条持久消息，确认后队列计数为 20；`docker compose restart rabbitmq` 后计数仍为 20。
- `docker compose start worker` 后，20 条任务全部通过真实网关成功，均尝试一次。实际批改中位数 1895 ms。
- 新任务进入 running 后执行 `docker compose kill -s SIGKILL worker`，再 `start worker`；默认 120 秒租约到期后自动恢复，第二次尝试成功，结果表只有一行。
- 向真实 RabbitMQ 重投已完成任务，任务仍 succeeded、attempts 仍为 1、结果仍一份；全表重复结果分组数为 0。

证据集中于 [week08](../docs/evidence/classroom/week08/)，包括 `clab-acceptance.json`、`broker-restart.json`、`clab-grading.json`、`clab-crash-recovery.json`、`clab-uniqueness.json`。数据均为合成资料和测试账号。

消费者执行次数记录实际取得租约的尝试；已成功任务的重复消息直接确认，不额外增加模型执行次数。外部模型调用在崩溃恢复时可能重复，结果只生效一次。
