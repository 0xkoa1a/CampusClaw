# 本机 HTTP API 验收

`run_all.py` 使用 Python 标准库，经真实 HTTP 调用已启动的 CampusClaw；它不会启动应用或创建测试数据库。`--database-path` 必须指向正在运行的这个实例实际使用的绝对 SQLite 文件，否则 HTTP 与数据库核对没有意义。数据库通过 SQLite `mode=ro` 打开。

运行前设置 `SEED_TEACHER_PASSWORD`、`SEED_STUDENT_A_PASSWORD`、`SEED_STUDENT_B_PASSWORD`。密码只从环境变量读入请求体，不写入文件或终端。Bearer token 只保存在该进程的内存上下文中。报告只记录 case 名、PASS/ERROR 和清洗后的错误摘要；不会记录请求/响应正文、技能源文或 token。运行报告写入 `apitest/reports/latest.html`，该目录已加入 Git 忽略。

```sh
export SEED_TEACHER_PASSWORD='…'
export SEED_STUDENT_A_PASSWORD='…'
export SEED_STUDENT_B_PASSWORD='…'
python3 apitest/run_all.py --base-url http://127.0.0.1:8080 --database-path /absolute/path/to/campusclaw.sqlite3
```

`--base-url` 仅接受 `http://localhost[:port]` 或 `http://127.0.0.1[:port]`。验收会新增以 `apitest-<随机前缀>` 命名的合成技能、智能体、会话和消息；会话及技能在用例末尾删除，智能体没有删除接口，会保留为合成数据。用例不上传、不检索发送任何已有私有材料；对话请求绑定无材料智能体，只包含合成提示词。

每个接口用例位于 `cases/api/<资源>/<HTTP方法>.py`，导出 `run(context)`；登录用例先运行，随后用例共享其内存 Bearer token 和生成的资源 ID。

## 第八课异步批改 HTTP 验收

runner 末尾依次运行三个新增 case：教师创建本班合成作业；学生使用 20 个独立 UUID 幂等键提交；轮询第一条任务直到 `succeeded`。作业、提交、任务、outbox 和批改结果会保留为合成验收数据。

- 提交 case 断言 20 次均返回 `202` 且响应不含 `result`，逐条只读核对 SQLite submission/task/outbox 的编号、归属与对应关系。
- `time_total_seconds` 测量每个 POST 从发起到响应正文读取完毕的耗时（不含后续 JSON 解析和 SQLite 核对）；`p95_seconds` 使用最近秩法：排序后取第 `ceil(20 × 0.95)` 项。两者写入 case 详情及 HTML 报告，供课程延迟判据核对，不以本机数值替代真实部署测量。
- 相同 key 与正文重提必须返回原 task/submission；同 key 换正文必须 `409`；B 班读取作业、提交答案和读取任务必须 `404`。这些操作后仍只能有原来的 20 条提交及其 task/outbox。
- GET case 默认使用 `--timeout` 作为整体轮询期限（默认 60 秒），遇到 `failed`/`dead` 或超时明确失败。成功后核对 HTTP 与 SQLite 的分数、反馈、来源，并确认按 task 和 submission 查询都只有同一条结果，重复 GET 不改变结果。自定义上下文可用 `grading_timeout` 单独设置轮询期限。

case 不会停止、启动或重启消费者，也不修改 `consumer.enabled`。应由操作者预先确认目标 worker 及批改模式。`test-provider` 只代表本地确定性测试替身；当前 18088 fixture 的内存传输不能证明 RabbitMQ 持久化、代理重启恢复或消息重投。真实代理和课程网关验收须另留实际证据；运行本地这组三 case 不需要调用对话网关接口。

只运行登录、身份核对与新增三个 case，可在已设置三项密码环境变量的终端使用下列入口。`APITEST_DATABASE_PATH` 仍须指向该 HTTP 实例的实际数据库；不会创建报告文件或运行旧会话 case：

```sh
export APITEST_DATABASE_PATH=/absolute/path/to/fixture/evidence.sqlite3
python3 - <<'PY'
import os
import uuid
from apitest.run_all import SECRET_NAMES, load_cases, validate_base_url

context = {
    "base_url": validate_base_url("http://127.0.0.1:18088"),
    "database_path": os.environ["APITEST_DATABASE_PATH"],
    "timeout": 60,
    "secrets": {name: os.environ[name] for name in SECRET_NAMES},
    "tokens": {}, "identities": {},
    "synthetic_prefix": "apitest-" + uuid.uuid4().hex[:12],
}
order = ("api/login/POST.py", "api/me/GET.py", "api/assignments/POST.py",
         "api/assignments/id/submissions/POST.py", "api/tasks/id/GET.py")
for name, run in load_cases(order=order):
    print("PASS", name, run(context))
PY
```
