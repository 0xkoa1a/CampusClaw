# 第 6 课参考资料：MCP 与工具接入

本目录整理截至 2026-10-21 在课程站点公开的第 6 课材料。课程首页在阶段三列出第 5、6 课的课件与任务清单，第 7、8 课仍标记为“课件待补充”；因此当前最新可用课程是第 6 课。此判断依据首页当前显示状态，不推断发布日或截止日期。

## 导航

- [要求与实现边界](requirements.md)：按课程任务清单、教程验收、建议和示例分类。
- [来源清单](sources/manifest.md)：记录入口、课件各页、任务清单、系统原型、Swagger 与 OpenAPI。
- [课程首页提取](sources/course-home.md)
- [任务清单提取](sources/course-tasks.md)
- [教程各页提取](sources/lesson-pages.md)

正文要求集中在 [requirements.md](requirements.md)，来源索引与链接集中在 [sources/manifest.md](sources/manifest.md)，逐页原始 HTML 快照保存在 [sources/html/](sources/html/)。快照按公开 URL 下载并记录 SHA256；页面引用的共享 CSS/JavaScript 和站点根路径资源未纳入本次 HTML 快照。原文链接仍以课程站点为准。

## 范围说明

课程任务要求在第 5 课仓库上增量实现：CampusClaw 主应用保持同一个项目，并在同一仓库新增 `mcp-server/`。仓库根目录的 `AGENTS.md` 还规定须先写并 Review OpenSpec 规约后再实现；这是仓库开发流程，不是课程网页新增的交付项。本次只归档课程资料，没有修改业务代码、提交 Git 或推送远端。
