# 第 5 课参考资料

本目录保存截至 2026-10-14 可公开访问的第 5 课详细教程、独立任务清单、Swagger 页面和 OpenAPI 描述，供之后实现时查阅。课程入口在 2026-09-18 的本地记录中把第 3–11 课标为待补充；本次已确认第 5 课现可访问。仓库没有第 5 课旧快照，现有旧 proposal 只提到“流式/长会话”，因此这些材料只能证明当前页面的可访问状态，不能据此断言具体内容何时新增或更新时间。

## 导航

- [详细要求与实现边界](requirements.md)：按原文归纳功能、数据、接口、权限、流式行为、OpenAPI、测试与验收，并标明要求来源。
- [来源清单与校验值](sources/manifest.md)：记录 URL、页面标题、采集时间、访问状态和 SHA-256。
- [课程入口 HTML](sources/course-home.html)
- [第 5 课教程概览 HTML](sources/index.html)
- [第 5 课任务清单 HTML](sources/course-tasks.html)
- [Swagger HTML](sources/swagger.html)
- [OpenAPI JSON](sources/openapi.json)

## 教程页面

以下链接指向逐页保存的原始 HTML。页面正文及表格均保留在原件中；HTML 中引用的图片和构建脚本没有下载。

| 页面 | 本地来源 | 内容定位 |
| --- | --- | --- |
| 预习：认证与知识库问答 | [preview.html](sources/pages/preview.html) | Cookie/Session、Bearer JWT、身份与授权边界、知识库问答 |
| 本课重点 | [scope.html](sources/pages/scope.html) | 六项工作、角色权限、DoD 与验证方法 |
| 会话与消息模型 | [session.html](sources/pages/session.html) | 会话归属、智能体锁定、历史窗口、消息持久化 |
| 智能体与技能的数据模型 | [skill-model.html](sources/pages/skill-model.html) | 字段、技能文件格式、样板、权限与生效时机 |
| 技能路由与消息组装 | [route.html](sources/pages/route.html) | 候选集、词法计分、系统/用户消息边界、材料范围 |
| 流式输出与 SSE | [stream.html](sources/pages/stream.html) | SSE 与 WebSocket 取舍、四类事件、缓冲和错误时序 |
| 一次回答的链路 | [answer.html](sources/pages/answer.html) | 十一步处理顺序、状态码边界、引用和持久化 |
| 实践步骤与验收 | [apply.html](sources/pages/apply.html) | 依赖顺序、逐层验收、故障排查、同伴交叉验证 |
| 思考与分析 | [think.html](sources/pages/think.html) | 五道研讨题及替代方案权衡 |

## 来源边界

课程原文是之后实现与验收的依据。`requirements.md` 把直接要求、页面举例和整理者推断分开；遇到详细教程、独立任务清单与 OpenAPI 描述的口径差异，应回到对应原件核对。公开系统原型入口只返回 React HTML 壳页，见 [prototype-shell.html](sources/prototype-shell.html)；本次未登录或访问课堂派，也未下载原型的 JavaScript、CSS 或图片资源。
