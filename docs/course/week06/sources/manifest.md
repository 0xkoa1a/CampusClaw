# 第 6 课来源清单

采集日期：2026-10-21（Asia/Shanghai）。通过课程首页当前导航定位第 6 课；逐页打开并阅读概览、全部教程页、任务清单、系统原型登录入口、Swagger 与 OpenAPI。表中 10 个教程页面和任务清单的 HTML 已按公开 URL 保存到本目录，并逐一与同 URL 响应校验 SHA256；其余原型/API 页面保留来源链接和检查记录。

| 页面/资源 | URL | HTML 快照 | SHA256 | 已检查内容 |
| --- | --- | --- | --- | --- |
| 课程首页 | <https://devops.hello1023.com/> | — | — | 教学进度；第 6 课最新可用、后续课件待补充 |
| 第 6 课实现教程概览 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/index.html> | [html/index.html](html/index.html) | `640063dd5fa90c323d9ea1bc35ae147b957c87563fd90ec33f52343893f4b6ab` | 两端交付、六个知识点、教程导航 |
| 预习：工具调用要解决什么 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/preview.html> | [html/pages/preview.html](html/pages/preview.html) | `234464a4c01fd76bec4b31f551d1dd1a0b054cc13eaca4ad8e6187935414ff00` | 动机、MCP 定位、相邻方案比较、本课两端 |
| 本课重点 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/scope.html> | [html/pages/scope.html](html/pages/scope.html) | `d39645b8d9d5b275cce55c23a19b8c022e5b2001e6a794f1e0f7079ec1d0a7cd` | 交付、验收和验证方法 |
| 协议的三层 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/mcp-model.html> | [html/pages/mcp-model.html](html/pages/mcp-model.html) | `8258e81ed6ed83332c50daee7bf1617876f458e25808955ae1c9e935f19860d4` | tools/resources/prompts、HTTP 与 stdio、JSON-RPC、握手与发现 |
| 工具声明与候选集 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/binding.html> | [html/pages/binding.html](html/pages/binding.html) | `8c1770e61073ce8eb31143df63e25d0091c58d746867e22ab19f2f9b9ebacef1` | 名称、说明、inputSchema、候选集、工具引用校验 |
| 调用循环 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/bridge.html> | [html/pages/bridge.html](html/pages/bridge.html) | `d1ad3a5f528b1e99e54ff7027cf7614c9f70bb1aef28e2652f445bae484a77f3` | 连接发现、调用循环、终止条件、失败处理 |
| 工具带来的风险面 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/security.html> | [html/pages/security.html](html/pages/security.html) | `e3848710e644243853c5336ff1a90269f205571d3993f484fb8bd3bd25ad5208` | 不可信返回、工具投毒、权限、配额、令牌边界 |
| 调用的可观测性 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/audit.html> | [html/pages/audit.html](html/pages/audit.html) | `4a23c2eec691adf3ab5a209551d89e96e0b877055735df0ae3913fce9e5753d0` | 调用记录字段、先发调用事件、管理界面 |
| 实践步骤与验收 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/apply.html> | [html/pages/apply.html](html/pages/apply.html) | `7d6a5c241d0ec5fc2d1e1f48f21f4c5cadd2d8b60c4f1dbb0d4965b48b811355` | 分层推进、故障定位、同伴交叉验证提示 |
| 思考与分析 | <https://devops.hello1023.com/课件/第6课-课件-MCP与工具接入/pages/think.html> | [html/pages/think.html](html/pages/think.html) | `4a727d63fa72b56d6efa7a3a3b1d91fe674326ad4d31b5ec6cd862b1f4f25d25` | 五个研讨问题、替代方案与权衡 |
| 第 6 课任务清单 | <https://devops.hello1023.com/课程任务清单-第6课.html> | [html/course-tasks.html](html/course-tasks.html) | `f53026a92543e103be6255a0730449b33a5447771e00105330492ba2b21e454e` | 同仓服务、接口、技能引用、审计、建议测试与自查 |
| 第 6 课系统原型 | <https://devops.hello1023.com/week06/> | — | — | 页面跳转至 `/week06/login`；未登录或操作 |
| Swagger UI | <https://devops.hello1023.com/week06/swagger/> | — | — | 确认 CampusClaw API 页面及 MCP 管理接口分组 |
| OpenAPI JSON | <https://devops.hello1023.com/week06/openapi.json> | — | — | 确认当前公开 OpenAPI 与 MCP 管理路径；该文档还包含以前课程的接口 |

## 来源边界

- 课程首页给出课程编号与课件发布状态；不能据此推出准确发布时间。
- 第 6 课任务清单决定实现范围。教程解释协议机制和设计取舍，未写入任务清单的替代方案不作为硬性验收要求。
- Swagger/OpenAPI 是课程原型的公开接口说明，不能把其中全部既有 API 视为第 6 课新增接口。
- 系统原型只检查到登录入口；未登录、未试调接口。未将原型的页面实现细节升格成课程要求。
- HTML 快照保留原始相对链接。教程页之间的页面链接可在 `html/` 目录内解析；共享 CSS/JavaScript 未归档。任务清单含站点根路径的课程导航链接，需在原课程站点上下文中解析，不能直接作为本快照目录内链接。
