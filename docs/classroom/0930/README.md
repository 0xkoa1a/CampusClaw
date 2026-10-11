# 身份认证与知识库问答报告

报告包含系统架构、Token 认证与权限控制、知识库解析与索引、检索问答与来源追踪，以及三张运行截图。

## 文件

- [Markdown](authentication-and-knowledge-qa.md)：报告源文件。
- [自包含 HTML](authentication-and-knowledge-qa.html)：图示、脚本、样式与截图已内联，可离线阅读。
- [PDF](authentication-and-knowledge-qa.pdf)：6 页 A4，带页码和书签。
- [打印样式](print.scss)：正文连续分页，运行截图单独分页。

## 导出方法

使用 `vuepress-notes-template` 的 `531b03d` 版本创建临时副本并安装依赖。Markdown 放在 `notes/classroom/0930/`，图片放在 `notes/evidence/classroom/0930/`，打印样式通过全局 index.scss 引入。

在 Node 22.18.0、pnpm 11.19.0 环境中执行：

```bash
make export PAGE=classroom/0930/authentication-and-knowledge-qa.md
```

严格导出得到自包含 HTML，再用 Playwright Chromium 按打印样式生成 PDF。导出结果复制到本目录后，运行 `python3 scripts/prepare_classroom_submission.py` 更新提交用 PDF 副本。

## 报告导出时的验证记录

- 删除课程、提交、日期、版本来源和部署免责声明；合并认证与权限说明，精简重复段落和图注。
- 模板标题检查、类型检查、8 项单元测试、站点构建和 4 项离线导出回归通过。
- 最终 HTML 的架构图和三张截图正常显示，目录跳转有效；1440 与 390 像素宽度无横向溢出，运行错误和外部 HTTP(S) 资源请求均为零。
- Markdown 与导出输入一致，HTML 与导出结果一致；导出脚本保留原始空白，由 .gitattributes 跳过生成文件的空白告警。
- PDF 共 6 页，已逐页检查正文、表格、图示、截图和页码。三张运行截图保留原始像素。
- 更新 [HTML 预览](../../evidence/classroom/0930/04-report-html-preview.png) 和 [PDF 首页渲染](../../evidence/classroom/0930/05-report-pdf-first-page.png)，与报告一同保存。
