## ADDED Requirements

### Requirement: 私有持久化会话
系统 MUST 固定会话的用户、班级与智能体，持久化消息、技能与引用；标题取首问前24字，历史只取最新六条有效消息、每条500字，本轮提问不得重复。

#### Scenario: 归属与历史恢复
- **WHEN** 用户新建会话、连续发送消息并刷新或重启
- **THEN** 历史 MUST 恢复；读取他人、跨班及不存在会话 MUST 返回一致404；请求另一个 agent_id MUST NOT 切换会话智能体

### Requirement: 真实 SSE 与故障收尾
系统 MUST 读取网关 stream=true 的真实增量，按 meta、delta、done 顺序输出；done MUST 在持久化成功之后。首事件前失败返回 HTTP 错误，之后发 error；中途失败或断连 MUST 保存 partial 内容并关闭上游；同会话并发发送或删除 MUST 返回409。

#### Scenario: 增量与数据库一致
- **WHEN** 网关发送中文和分帧引用文本
- **THEN** 拼接 delta MUST 等于入库正文，引用 MUST 有效，done MUST 包含真实消息ID

#### Scenario: 失败与并发
- **WHEN** 上游中断、浏览器断连或同会话再次发送
- **THEN** 已输出内容 MUST 保存为partial，资源与锁 MUST 释放；并发请求 MUST 返回409

### Requirement: 无资料回答与解题引导
新增会话链路 MUST 在无资料时仍生成且引用为空，并移除编号；命中解题引导 MUST 要求不直接给最终答案。上传资料 MUST 作为数据放用户消息，权限 MUST 由服务端判定。

#### Scenario: 无资料与引导
- **WHEN** 会话检索为空或命中解题引导
- **THEN** 无资料 MUST 调用模型且不含引用编号；引导提示 MUST 包含禁止最终答案要求，真实模型验收 MUST 人工检查输出

### Requirement: 可试调接口与可复现验收
系统 MUST 提供处理器注解生成的 OpenAPI、同源 Swagger Bearer 试调及逐接口 apitest，核对响应和数据库；报告 MUST 不入 Git。验收 MUST 包含真实网关与真实同伴记录。

#### Scenario: 文档和报告
- **WHEN** 执行接口测试并打开Swagger
- **THEN** 路由与文档 MUST 一致，报告 MUST 脱敏且被Git忽略，接口 MUST 可用Bearer试调

#### Scenario: 同伴验收
- **WHEN** 独立同伴账号验证归属、智能体隔离、班级边界和技能开关
- **THEN** 真实请求/响应 MUST 留档，缺失时变更 MUST 保持活跃
