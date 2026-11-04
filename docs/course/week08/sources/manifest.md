# 第 8 课来源清单

采集日期：2026-11-04（Asia/Shanghai）。七份原始 HTML 来自课程网站的真实 HTTP 下载；归档文件按字节复制。SHA-256 针对归档副本计算。

| 页面 | 来源地址 | 快照 | SHA-256 | 核对范围 |
| --- | --- | --- | --- | --- |
| 第 8 课教程概览 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/index.html> | [lesson.html](lesson.html) | `6f0a977f97657d852fa2a3145cf1ea0268800df170ada3a4eaae97a0f6456049` | 同步问题、异步契约、队列职责、三条验收判据与主线导航 |
| 第 8 课任务清单 | <https://devops.hello1023.com/课程任务清单-第8课.html> | [course-tasks.html](course-tasks.html) | `d6bf66aa642a1f6cf0528cb140173346b157da6b73009eaa203beee6335028f3` | 安全自查范围、异步并发与事务证据要求、演示链路和核查项 |
| 异步：契约与状态 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/pages/async.html> | [pages-async.html](pages-async.html) | `a3c34a24a0fcd9820aaa3d997df440a0a6ffd65f583a6ecc3e5112a00efa9aee` | 提交/查询 API 示例、四态状态机、任务最低字段 |
| 消息队列：语义与机制 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/pages/queue.html> | [pages-queue.html](pages-queue.html) | `66a446f4eddca2fd9ade07fcec05090f628c2fcdf4e2a6a44b77296efcf171ce` | 队列语义、至少一次投递、ACK/重投、Redis 与 RabbitMQ 选型 |
| 系统改造：架构与任务模型 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/pages/redesign.html> | [pages-redesign.html](pages-redesign.html) | `ba16e2a80a172ddde8b4c7afd7a6d72ec4970112fcc5383e9a36197e09f3c2d4` | 任务字段、事务性发件箱、投递器与查询职责 |
| 失败重试与幂等 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/pages/retry.html> | [pages-retry.html](pages-retry.html) | `e0b5f3fb47116f8e1f5e15f19b7a5154f7198b3e0561f505559342b282e5075b` | 失败分类、指数退避与抖动、死信、幂等唯一约束 |
| 实践步骤与验收 | <https://devops.hello1023.com/课件/第8课-课件-异步任务与消息队列/pages/apply.html> | [pages-apply.html](pages-apply.html) | `3ac0c7befb5cec1e41f89d7438596ab6758e0f7a2cd6ac8f22954e52908a4890` | 五步改造、20 次请求 P95、消费者停启与重复投递判据 |

原始网页按字节保存于 `sources/`，未下载共享样式和脚本。
