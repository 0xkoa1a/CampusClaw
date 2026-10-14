# 第 5 课来源采集清单

采集时间：2026-10-14 10:03–10:06（Asia/Shanghai；以本轮 HTTP 请求时间为准）。HTML 与 JSON 通过 `curl` 直接从公开站点获取并保留原始响应实体；未将浏览器文本伪称为原始 HTML。网页 `Date` 响应显示采集时刻约为 2026-10-14 02:03–02:05 UTC。SHA-256 针对本地保存文件计算。

| 本地文件 | 页面标题/资源名 | URL | HTTP | SHA-256 |
| --- | --- | --- | ---: | --- |
| [course-home.html](course-home.html) | 互联网软件开发技术与实践 - 课程入口 | <https://devops.hello1023.com/> | 200 | `fb7a683f8765af43d64fa04dae4fc996dad0477ca671a6fc06af224626769aa7` |
| [index.html](index.html) | CampusClaw 第 5 课 · 实现教程 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/index.html> | 200 | `e54753f56a277b907049ce1a6ddb16de9a1bb20d9db3ba312fc9432126b36d04` |
| [pages/preview.html](pages/preview.html) | 认证与知识库问答 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/preview.html> | 200 | `178544e53c3f679245976c525b64a6cc5ab395e1a551ddfdb2888f02454eb822` |
| [pages/scope.html](pages/scope.html) | 本课重点 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/scope.html> | 200 | `1ab1fa0d336f8cb0a53dc42b6831b10ba193e9856ee89c7f7f530d16aec0a56e` |
| [pages/session.html](pages/session.html) | 会话与消息模型 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/session.html> | 200 | `7716aa7021acb078e775b267cd5b60d9558fcff92e9e402857aab134f51b802e` |
| [pages/skill-model.html](pages/skill-model.html) | 智能体与技能的数据模型 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/skill-model.html> | 200 | `4821bd2629abd146568ea73c67ad5a05153dec698572f4715c3503e61948f224` |
| [pages/route.html](pages/route.html) | 技能路由与消息组装 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/route.html> | 200 | `b0d6f748dbea7a272bfd75a4f510837c39edfee0eb525e2df1ab7c3e95f216cd` |
| [pages/stream.html](pages/stream.html) | 流式输出与 SSE | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/stream.html> | 200 | `8d7e8c82f6b7ee26556e521816716f346021f0648c5db9bccf7d618e1932f2b5` |
| [pages/answer.html](pages/answer.html) | 一次回答的链路 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/answer.html> | 200 | `a29eebb315a8751652733d90066948258c7e962379b9817760c49e63141295a9` |
| [pages/apply.html](pages/apply.html) | 实践步骤与验收 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/apply.html> | 200 | `b783a64e7ea5db0d049434f5d45881e9e44c584b7f77867d3d10f60ff90ff884` |
| [pages/think.html](pages/think.html) | 思考与分析 | <https://devops.hello1023.com/课件/第5课-课件-提示词AI技能与流式会话/pages/think.html> | 200 | `3f13be3630c008bb06691e32df95ee22dd00df8aff495ae99500bdb1dd01ffad` |
| [course-tasks.html](course-tasks.html) | 第 5 课任务清单 | <https://devops.hello1023.com/课程任务清单-第5课.html> | 200 | `6558a67df4a24d717c423cc57814b0ab37e46bc1d3fce872340b5f3e60b58062` |
| [swagger.html](swagger.html) | CampusClaw API | <https://devops.hello1023.com/week05/swagger/> | 200 | `411d8190cc251ce59a6b7f1b40d276c503d7958ddf4ef150bff31a413b524c6f` |
| [openapi.json](openapi.json) | CampusClaw API · OpenAPI 1.0.0 · 34 paths | <https://devops.hello1023.com/week05/openapi.json> | 200 | `688bdcab0efea87ae73e5b005475505cee653542f4627ce843f59c8767f6e4f1` |
| [prototype-shell.html](prototype-shell.html) | CampusClaw 原型入口 HTML 壳页 | <https://devops.hello1023.com/week05/> | 200 | `af395f6fbe098a3d29c31d3d2034022fc643a1a2cde9d4d3360c78c645a92336` |

入口首页响应包含 `Last-Modified: Tue, 13 Oct 2026 14:04:08 GMT`。该字段只记录课程入口首页的 HTTP 元数据，不代表第 5 课页面更新时间；本轮未发现可供比较的第 5 课历史快照。原型入口仅保存返回的 HTML 壳页，没有下载其 JavaScript、CSS 或图片。课程页内导航和反向链接重复指向上述页面，没有发现额外的第 5 课文字附件；课程任务页所列 Swagger 与 OpenAPI 已单独检查并保存。
