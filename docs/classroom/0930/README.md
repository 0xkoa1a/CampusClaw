# 0930 课后方案文档

用于“整理身份认证以及知识库问答的实现方案”。平台要求提交 PDF；截止时间在 [要求留档](../requirements.md) 中为 2026-10-15 00:00。文档覆盖实际 JWT 登录与会话撤销、角色和班级授权、材料切片与索引、本班检索、模型回答和来源高亮，并保留实现与验收边界。

## 文件

- [Markdown 原稿](authentication-and-knowledge-qa.md)：后续修改的源文件，包含与标题一致的 VuePress frontmatter。
- [自包含 HTML](authentication-and-knowledge-qa.html)：VuePress 严格导出，脚本、样式、图示与三张原有截图均已内联，可以离线阅读。
- [PDF](authentication-and-knowledge-qa.pdf)：9 页 A4，章节分组，带页码和书签；用于学生自行提交课堂派。
- [打印样式](print.scss)：本次报告专用的分页和排版设置，已包含在 HTML 中。

HTML 的外部普通超链接仍需要联网或平台登录。运行截图保留原始分辨率，PDF 中可放大核对；原图也保存在 `docs/evidence/classroom/0930/`。

## 制作路径

实际模板仓库是 `/Users/yangyixin03/Workspace/vuepress-notes-template`，使用版本 `531b03d` 的 README 和导出器。开始时该仓库已有三处 skill 文档修改，因此从该版本创建临时副本，复用已安装依赖，在副本中完成报告导出；原仓库的未提交修改未纳入构建，也未被修改。

Markdown 在副本中放到 `notes/classroom/0930/authentication-and-knowledge-qa.md`，三张已有截图复制到 `notes/evidence/classroom/0930/`，保持相对图片路径一致。将本目录 print.scss 放入副本的 `notes/.vuepress/styles/0930-print.scss`，再由全局 index.scss 引入，未添加文章内样式。

在 Node 22.18.0、pnpm 11.19.0 环境中使用 README 的 `make export PAGE=classroom/0930/authentication-and-knowledge-qa.md`。临时副本复用相同锁定依赖，关闭 pnpm 的运行前自动安装，以免重写原仓库依赖。导出保持严格模式，包含离线 CSP 和网络守卫。

HTML 导出成功后复制回本目录。使用已有 Playwright Chromium 打开最终 HTML，等待图示、字体和图片就绪，按打印媒体转换为 PDF，采用 print.scss 的 A4 边距、背景和分页设置，添加页码并生成可访问标签与书签。PDF 内容来自实际渲染后的 HTML。

## 验证

- 当前 CampusClaw 自动化测试：51 项通过；OpenSpec strict：3 项通过。
- 模板副本：标题检查、TypeScript / Vue 类型检查、8 项单元测试、站点构建及 4 项离线导出回归通过。
- 最终 HTML：三张图片和一张架构图正常显示；目录实际点击跳转成功；1440 与 390 像素宽度没有横向溢出；运行错误与 HTTP(S) 资源请求均为零。
- 最终 Markdown 与导出输入逐字一致，HTML 与模板导出结果逐字一致。
- 手写文件通过 Git 空白检查；导出 HTML 的内联第三方脚本保留原始空白，由专用 .gitattributes 规则跳过空白告警，避免改写 JavaScript 字符串。
- PDF：9 页 A4，三张原有证据图完整嵌入；检查全部页面的标题、正文、表格、截图和页码。字体与架构图可缩放，截图保留原始像素。
- 本次生成的 [HTML 预览截图](../../evidence/classroom/0930/04-report-html-preview.png) 与 [PDF 首页渲染](../../evidence/classroom/0930/05-report-pdf-first-page.png) 随报告一同留档。

报告制作完成后清理临时副本、构建产物和检查用页面图，核对原模板的 Git 状态及已有 diff 与开始时一致。原模板原有的三处未提交修改保留。

本地 commit、GitHub push 和课堂派提交是各自独立的操作。该目录交付报告文件，平台提交由学生本人处理。
