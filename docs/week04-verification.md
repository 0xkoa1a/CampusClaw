# 第四课验收记录

记录日期：2026-09-30。依据[正式规格](../openspec/specs/traceable-retrieval/spec.md)验收可追溯检索。课程网关密钥只保存在 CLab 私有 `.env`，权限 0600；仓库不含密钥。

## 自动化与界面

- `python -m pytest -q`：32 项通过，含切片原文偏移、历史库迁移、上传索引失败后重试、三种检索、跨班 point 拒绝、无证据不调用对话模型、引用编号、权限与服务故障测试。
- `openspec validate --all --strict`：归档后两份正式规格均通过。`docker compose config -q` 用本地占位环境变量通过，`git diff --check` 通过。
- 本地材料页浏览器验收：桌面与手机宽度下检索、来源链接、原文高亮可用；手机宽度无横向溢出，控制台无错误。浏览器验收使用本地测试账号与模拟模型；真实网关另在 CLab 验证。

## CLab 真实服务

在 Ubuntu 24.04 CLab 上使用课程网关、Qdrant 与真实 Compose 容器。执行批量向量化前，逐字核对了全部 3 份既有材料：两份预置 A/B 班演示文案，以及一份第三课脚本生成的合成验收文案。没有将其他材料发往网关。

- `python -m scripts.reindex_all`：3 份材料、3 个切片全部变为 `ready`。
- `python -m scripts.verify_deployment before`：登录、班级权限、合成材料上传与文件校验通过，新增材料 ID 4。
- `python -m scripts.verify_retrieval`：关键词、向量、混合检索和真实对话回答通过；引用对应本班来源，跨班访问拒绝，来源链接定位原文。Qdrant 共有 4 个 point，ID 与 SQLite 切片一致，payload 只有标识字段，没有正文。
- 执行 `docker compose down`、`docker compose up -d --wait`，保留命名 volume。之后 `scripts.verify_deployment after` 与 `scripts.verify_retrieval` 再次通过；4 份材料、4 个知识库记录、2 个上传文件与 4 个向量 point 均保留。
- 应用与 Qdrant 容器健康；应用端口只绑定 `127.0.0.1:8080`，Qdrant 不映射宿主机端口。

`scripts.verify_retrieval` 只允许上述合成材料集合；发现其他正文即退出。对真实材料使用课程网关前，应先确认数据授权范围。无证据回答与向量故障降级由自动化测试验证，未通过临时关闭线上服务制造故障。
