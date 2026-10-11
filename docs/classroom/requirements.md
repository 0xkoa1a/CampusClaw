# 课堂派作业要求留档

来源：用户已登录 Chrome 中的[课程作业列表](https://w.ketangpai.com/courseHome?courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0&tabActive=4)。逐项打开十个活动，阅读所有正文和截图示例，按作业日期整理。下文引用块保留作业正文；示例部分描述图片实际内容，认证值和示例密码不留档。平台详情需要相应课程账号登录。

每项均为个人作业，页面标示 100 分。采集时 0930 课后任务为“未提交”，其余九项为“已结束／未参与”。GitHub 留档与课堂派提交是两项操作，平台提交及补交由学生本人处理。

## 提交类型总览

| 作业 | 平台截止时间 | 要提交的内容 | 示例数量 |
| --- | --- | --- | --- |
| 0923 系统运行截图 | 2026-09-23 12:00 | 一张教师登录后的首页截图 | 1 |
| 0923 登录 HTTP | 2026-09-23 12:00 | 请求参数、响应结果、完整响应头截图 | 3 |
| 0923 登录后身份识别 | 2026-09-23 12:00 | 获取班级材料时的身份识别截图与分析 | 1 |
| 0923 上传逻辑与类型 | 2026-09-23 12:00 | 实现逻辑分析结果 | 0 |
| 0923 下载权限与逻辑 | 2026-09-23 12:00 | 分析结果，以及未授权下载失败截图 | 0 |
| 0923 后端 API 访问 | 2026-09-23 12:00 | 根据 Compose、Dockerfile、配置分析访问方式 | 3 |
| 0923 课后任务 | 2026-09-30 00:00 | 含第四课 OpenSpec 变更的开放仓库地址 | 0 |
| 0930 token 登录 | 2026-09-30 12:00 | 实现效果截图，示例展示 Bearer JWT 请求头 | 1 |
| 0930 知识库 AI 问答 | 2026-09-30 12:00 | 页面仅提供带来源引用的问答效果示例 | 1 |
| 0930 课后方案整理 | 2026-10-15 00:00 | 基于现有代码的 token 认证和知识库问答方案 PDF | 0 |

## 0923-系统运行截图

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92GubevhqVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 直接发送一张教师登录后的首页截图

示例：A 班教师 teacher_a 登录后的 CampusClaw 首页，含材料列表、正文、上传入口和下载原文件按钮。没有要求学生首页；已有 `docs/evidence/classroom/0923/peer-verification/peer-teacher-upload.png` 已覆盖教师身份、材料和上传功能。

## 0923-系统登录时的请求参数以及响应结果以及HTTP响应完整内容

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92GubewhbVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 通过截图提供
>
> 请求参数
>
> 响应结果
>
> HTTP协议响应header完整内容

三个示例均为浏览器 Network 中的 login 请求：载荷页展示 username、password；响应页展示 class_id、role、username 的 JSON；标头页展示 POST、200 OK 和完整响应头，包括 Content-Type、Content-Length、Date、Server、Set-Cookie 等。Cookie 示例属性含 Path=/、Max-Age、HttpOnly、SameSite=Lax。字段应按本人系统真实响应展示，不应伪造为老师示例的服务版本或有效期。

## 0923-用户登录成功以后，用户身份识别方式

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92GubdphaVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 截图分析，用户登录成功后，在发起获取班级材料的请求时，如何识别用户的标识。

示例：Network 中 materials 请求的请求标头，突出 Cookie: session=…，借此解释服务端如何识别已登录用户。需要保留 Cookie 方案的真实证据，与 0930 的 Bearer 实现区分。

## 0923-文件上传逻辑？支持哪种文件类型？txt，md以外文件是否支持？

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92GubtrhdtyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 可以借助AI来分析实现逻辑，提交分析结果

没有截图示例，正文未要求上传截图。分析需回答支持类型、格式以外的校验、权限、解析与入库，以及失败处理。

## 0923-文件下载是否需要权限？实现逻辑？

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92GubtshLVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 可以借助AI分析结果。并截图验证未授权情况下不能访问文件。

没有截图示例。必须证明未授权访问失败；仅有下载按钮不构成这项证据。本人系统分别以未登录 401 和跨班 404 验证。

## 0923-后端（api）是否暴露给用户？如何通过浏览器直接访问后端接口

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92Gub-yhctyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 可通过查看 dockercompose文件以及dockerfile文件及相应的配置文件来分析

三个示例：Compose 的 api 服务没有宿主机端口映射（红字“后端没有暴露端口”）；nginx.conf 将 /api/ 反向代理到 http://api:8000/api/；示例环境配置区分后端 PORT=8000 与 Web WEB_PORT=8088。

这里需要分析本人代码。老师示例为独立 API + Nginx，本仓库为 Flask 同时提供页面和 API，不能照抄“不暴露后端端口”的结论。

## 0923-课后任务

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92Gub9phLVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 完成第四次课的openspec的变更描述。
>
> 基本要求：实现限定班级范围的知识库检索，支持内容溯源，可以考虑使用向量数据库来存储。
>
> 提交一个开放的仓库地址，仓库中包含本次变更内容。

没有截图示例。准备提交的仓库：[0xkoa1a/CampusClaw](https://github.com/0xkoa1a/CampusClaw)。现有 `openspec/changes/archive/2026-09-30-add-traceable-vector-retrieval/` 和正式 `openspec/specs/traceable-retrieval/spec.md` 保存变更与规格。

## 0930-课堂任务-toekn方案实现登录认证

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92IqadphKVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 请截图提交实现效果

标题保留平台原文的“toekn”。示例：已登录的 A 班学生页面与 Network materials 请求，突出 Authorization: Bearer JWT。正文没有另写 JWT 细则；按示例判断，应提供真实 Bearer 请求，原有 Cookie 图不能充分对应。

## 0930-课堂任务-基于知识库的AI问答

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92IqauyhbVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

页面没有额外文字要求，仅一张示例图。示例内容：A 班知识问答页面，问题“磁铁能吸木块吗？”，回答“磁铁不能吸引木块。[1]”；下方引用 `[1] A班-小学科学课程资料.md`，含切片编号、原文偏移和摘录。图中说明只检索本班 top 4 片段，无证据不调用模型。

据示例应准备问题、实际模型回答、引用编号、材料标题和来源的效果图；本仓库来源链接还可打开正文高亮。合成材料可用于截图，不必复制老师原材料。

## 0930-课后任务-整理身份认证以及知识库问答的实现方案

[原页面](https://w.ketangpai.com/homework?id=MDAwMDAwMDAwMLR2z92IqatshLVyoQ&courseId=MDAwMDAwMDAwMLOcx5aH37ewhbVyoQ&courseRole=0)

> 结合现有代码梳理基于token的身份认证以及基于知识库问答的实现方案。
>
> 提交PDF格式文档。

没有截图示例。截止 2026-10-15 00:00。此项需要独立 PDF，截图集合不替代方案文档。配套 [方案 PDF](0930/authentication-and-knowledge-qa.pdf) 已准备；这里只记录材料准备情况，课堂派提交由学生本人处理。

## 本次留档范围

截图文件、对应作业和验证边界见 [证据索引](evidence.md)；上传、下载与部署访问的分析见 [实现分析](implementation-analysis.md)。原页面的示例只记录内容说明，未把老师示例中的认证值、密码及签名资源 URL 提交到公开仓库。
