# 流水线与镜像追溯

修复提交 `bd68f97143951041a6960fc627b750deb2dfc809` 的两条 GitHub Actions 均已成功：

| 流水线 | 运行编号 | 结果 |
| --- | --- | --- |
| CI | [43905787819](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905787819) | `make check`、`make check-security` 成功 |
| Build and publish container | [43905786752](https://github.com/0xkoa1a/CampusClaw/actions/runs/43905786752) | gates 成功后 build 成功 |

发布镜像为 `ghcr.io/0xkoa1a/campusclaw:sha-bd68f97`，摘要为 `sha256:2af44789c3eee892cdde205af5c1a96d77c8d80d8939a0ed9fa385d6e8635856`。构建日志同时记录 `main` 与提交标签，Dockerfile 的 OCI revision 使用完整提交号。CLab 使用同提交源包和服务器配置本地构建，实际镜像 ID 另见 [clab-runtime.json](week10-local/clab-runtime.json)，不与 GHCR 摘要混用。

容器 job 依赖 gates，安全和功能检查未过时不会构建发布。首轮 `d57adc5` 因观测时间边界用例失败，CI 与容器 gates 均报红；修复后上表两次运行变绿。原始状态为 [ci-green.json](week10-local/ci-green.json)、[container-green.json](week10-local/container-green.json)，先红后绿见[门禁记录](gate-red-green.md)。

工作流保存在 `.github/workflows/ci.yml` 与 `container.yml`。主干分支保护属于团队仓库设置，本次未修改；当前仓库沿用已授权的直接提交、自动推送流程。
