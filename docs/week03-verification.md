# 迭代 1 验收记录

记录日期：2026-09-23。本仓库沿用第二课已评审的 Flask + SQLite 方案。第三课的 Go + MySQL 是教程示例；具体交付以本仓库 [正式规格](../openspec/specs/auth-upload/spec.md) 为准。规划和 26 项已完成任务保存在 [归档变更](../openspec/changes/archive/2026-09-23-add-auth-rbac-class-knowledge/)。

## 已验证

在仓库根目录安装 `requirements-dev.txt` 后运行：

```sh
python -m pytest -q
openspec validate add-auth-rbac-class-knowledge --strict
```

以上 change 校验在归档前执行。归档后使用 `openspec validate --all --strict`，输出为 `1 passed, 0 failed`；同步后的主规格与 delta 的全部 Requirement 和 Scenario 一致，`openspec list --json` 无活跃变更。

最终输出分别为 `24 passed`、`Change 'add-auth-rbac-class-knowledge' is valid`。其中 22 项为业务测试，新增 2 项覆盖 `.env` 的随机值、0600 权限、拒绝覆盖和镜像参数校验。以下六条关键 Scenario 可以用 `python -m pytest -q` 加上对应测试路径单独复核：

| Scenario | 测试路径 | 判定 |
| --- | --- | --- |
| 未登录请求材料接口不会得到业务数据 | `tests/test_app.py::test_health_and_anonymous_rejected` | 通过，接口 401；`/health` 200 |
| 学生上传被拒且库与目录无变化 | `tests/test_app.py::test_student_upload_rejected_without_side_effects` | 通过，403；两表与目录无变化 |
| A 班列表不含 B 班标题，跨班详情与不存在同形 | `tests/test_app.py::test_class_isolation_and_tampering` | 通过，跨班详情/文件/页面均为 404 |
| 教师上传后本班可查、学生可下载、B 班不可见 | `tests/test_app.py::test_teacher_upload_visible_to_own_class_and_download` | 通过，材料与知识库各新增一行 |
| 数据库第二步写入失败不留孤儿文件或行 | `tests/test_app.py::test_database_failure_rolls_back_and_removes_file` | 通过，500；事务回滚、文件删除 |
| 重新创建应用实例后数据仍可读 | `tests/test_app.py::test_restart_preserves_uploaded_data` | 通过，测试同一 SQLite 文件的本地进程重启语义 |

Playwright 在 `http://127.0.0.1:8765` 的临时本机服务上验证了登录页 → 教师登录 → 上传 Markdown → 列表与详情刷新可见 → 登出；桌面 1440×900 与手机 390×844 均无横向溢出，最终控制台错误为 0。该测试环境使用一次性本地密码与 `/private/tmp` 下的数据库和上传目录，不是 Compose 环境。

## Compose 实测

2026-09-23 在全新的 PKU CLab Ubuntu 24.04.3 amd64 环境按 README 从零启动。Docker Engine 29.1.3，Compose 2.40.3。校园网关登录后 Docker Hub 仍超时，使用 AWS ECR 托管的 Docker 官方镜像 `public.ecr.aws/docker/library/python:3.12-slim`，拉取摘要为 `sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`。构建成功，容器以 UID 10001 运行并达到 healthy，端口绑定 `127.0.0.1:8080`。服务器 `.env` 权限确认为 0600。

按 README 执行 `scripts.verify_deployment` 的 before/after 两阶段，中间真实执行 `docker compose down` 和 `docker compose up -d --wait`。逐项对照 Scenario 并检查脚本断言与实际响应：

| 验收项 | 实测结果 |
| --- | --- |
| 未登录健康检查、登录页、材料接口 | 分别为 200、200、401 |
| 三个预置账号 | 角色及班级正确，重建后均可重新登录 |
| 学生上传、教师非法格式上传 | 403、400，用户/材料/知识库数量及上传文件集合不变 |
| A 班访问 B 班的详情、下载、页面 | 404，接口详情与下载的响应和不存在资源一致 |
| 教师上传时伪造 `class_id=2` | 创建材料 ID 3，材料与知识库仍归 A 班 |
| 同班学生读取列表、正文、下载 | 均成功，伪造查询班级参数不能查看 B 班 |
| B 班访问新材料 | 列表不含新材料，详情和下载均为 404 |
| 登出 | 随后 `/api/me` 返回 401 |
| 重建持久化 | 两阶段均 PASS，保留 3 个用户、3 条材料、3 条知识库记录和 1 个上传文件 |

重建前容器 ID 前缀为 `689c65eaf81c`，重建后为 `fb610042a947`，确认测试包含容器替换。前后下载文件 SHA-256 一致：`4306b1d43ad478d8627e4aa9033dc0f756ddef4379e03c35b4fbb92eb8e319a6`。两阶段通过数据库关联查询确认材料、知识库的班级和正文一致。测试保留一份合成材料供演示。

## 同学交叉验收与提交

上述结果由本仓库自动化测试和部署验收脚本产生。课程要求的另一位同学交叉测试尚未进行，需要同学独立验证并记录姓名、日期、操作和结果。

- 同学在自己的副本按 README 从零启动，或在获授权的访问方式下测试演示服务。
- 使用学生 A1 登录，篡改 URL 访问 B 班材料 `/api/materials/2`，检查 404 且不包含 B 班正文。
- 尝试上传，检查 403；再用教师 A 上传，确认学生 A1 可见、学生 B1 不可见。
- 复核重建持久化命令，并记录结果。不要共享个人服务器私钥或校园网密码。

26 项实现任务已完成，主规格已同步，change 已归档；课程交叉验收仍保留在此处待补。GitHub push 和课程平台提交由用户确认后执行。
