# 安全基线

执行于 2026-11-04，本地工作区及 CLab 第八课隔离项目。只记录实测，不修改依赖或修复第 9、10 课发现项。

## 密钥扫描

```sh
.venv/bin/python scripts/security_baseline.py
.venv/bin/python scripts/security_baseline.py --history
```

两次均退出 0、无模式命中。首次统计当前可扫描源文件 251 份、可达历史源文件 blob 273 份；后续提交新增材料会改变文件数。脚本输出仅路径、行号和类别，不输出匹配正文。

范围包括 Git 跟踪及未忽略的新源文件、前端静态源码、Markdown/文本报告，以及本地所有 Git refs 可达的去重历史源文件 blob。历史可扫描误提交的 `.env`；当前私有 `.env` 不读取。排除二进制、vendor、虚拟环境和大于等于 2 MiB 的历史 blob。应用没有前端打包步骤，浏览器直接读取静态 JS/CSS。

扫描器使用高置信令牌格式和私钥标记，不覆盖任意随机字符串、截图像素或不可达 Git 对象。CLab 第八课运行日志另外使用实际配置中的 secret 字面值比对，结果见下文；上述范围均无命中。

## 依赖审计

```sh
uvx --from pip-audit pip-audit --requirement requirements-dev.txt \
  --requirement mcp-server/requirements.txt --format=json
```

本地清单在线审计扫描 18 个依赖条目，退出 1。原始输出中的两个条目对应同一项 pytest 公告，去重后发现 1 项：

| 依赖 | 被审计版本 | 公告 | 公告修复版本 |
| --- | --- | --- | --- |
| pytest | 8.4.2 | PYSEC-2026-1845 / CVE-2025-71176 / [GHSA-6w46-j5rx-g56g](https://github.com/advisories/GHSA-6w46-j5rx-g56g) | 9.0.3 |

该公告描述 UNIX 临时测试目录可能导致本地拒绝服务或权限提升。pytest 属于开发测试依赖，应用镜像只安装 `requirements.txt`。当前清单限制 pytest `<9`；后续修复需单独验证兼容性。本轮没有升级依赖。

工具未提供可靠的严重性分级，本报告不推测严重性。脱敏汇总见 [dependency-audit.json](dependency-audit.json)。

CLab 第八课实际应用镜像另行审计，依据 [image-audit.json](../docs/evidence/classroom/week08/image-audit.json) 和 [installed-requirements.txt](../docs/evidence/classroom/week08/installed-requirements.txt)：18 个已安装包中报告 12 条，按公告去重为 6 项，均对应镜像内 pip 25.0.1。该结果与本地开发清单中的 pytest 公告分开统计；本地 1 项仍保留。工具结果没有可靠严重性分级，不推测等级。本轮不升级依赖；SEC-06 为红。

## CLab 运行日志

第八课隔离项目为 `/home/ubuntu/workspace/campusclaw/verification/week08`，Compose 项目 `campusclaw-week08-20261104`，服务只绑定 loopback 端口 18088。按实际环境 secret 字面值与格式扫描运行日志，0 命中；结果见 [runtime-metadata.json](../docs/evidence/classroom/week08/runtime-metadata.json)。[worker-events.json](../docs/evidence/classroom/week08/worker-events.json) 记录 21 个批改事件，耗时中位数 1895 ms，范围 1100–5081 ms。

MCP 审计仍缺少耗时和用量字段，SEC-07 为红。第 9、10 课修复暂缓。
