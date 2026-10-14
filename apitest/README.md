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
