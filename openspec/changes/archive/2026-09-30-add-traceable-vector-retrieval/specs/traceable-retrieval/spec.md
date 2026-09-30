# traceable-retrieval Specification

## ADDED Requirements

### Requirement: 原文可追溯的切片索引

系统 MUST 保留上传的原始正文，在关系库保存切片正文、材料标识、班级、序号和原文位置，并以相同 ID 将向量存入私有 Qdrant。历史材料 MUST 能迁移并索引，教师 MUST 能重建本班材料索引。

#### Scenario: 上传与历史材料建立切片

- **WHEN** 教师上传合法材料或系统加载第三课已有材料
- **THEN** 原文 MUST 保持不变，切片 MUST 指回该材料的原文位置
- **AND** 可成功向量化的切片 MUST 在 Qdrant 有相同 ID 的 point，point payload MUST NOT 包含正文

#### Scenario: 网关失败后重试

- **WHEN** 上传后的向量化失败，教师稍后重建该材料索引
- **THEN** 上传记录和原文 MUST 仍可读取，索引状态 MUST 显示失败
- **AND** 重建成功后 MUST 清理旧切片与旧 point，状态 MUST 转为就绪

#### Scenario: 重建权限

- **WHEN** 学生尝试重建索引或 A 班教师指定 B 班材料
- **THEN** 学生 MUST 得到 403，跨班材料 MUST 得到与不存在材料相同的 404
- **AND** 请求 MUST NOT 修改该材料的切片或向量

### Requirement: 三类班级内检索

系统 MUST 提供关键词、向量和混合检索。关键词只查询关系库，向量查询 Qdrant 后 MUST 回关系库复核；混合模式 MUST 使用 RRF 融合已过滤的候选。所有模式 MUST 使用登录会话的班级并返回可点击来源。

#### Scenario: 短中文关键词与语义查询

- **WHEN** 本班用户用两个汉字检索原文关键词，或使用语义相近的不同表达进行向量查询
- **THEN** 关键词模式 MUST 能命中包含该词的本班切片，向量模式 MUST 返回满足阈值的本班切片
- **AND** 命中 MUST 包含标题、切片序号、摘录、原文位置和来源链接

#### Scenario: 伪造班级和跨班向量

- **WHEN** A 班用户在请求头、查询参数或 JSON 中传入 B 班 ID，且 Qdrant 返回 B 班 point
- **THEN** 服务 MUST 忽略客户端班级并剔除 B 班结果
- **AND** 响应 MUST NOT 包含 B 班正文或标题

#### Scenario: 向量服务不可用

- **WHEN** Qdrant 故障而关系库可用
- **THEN** 关键词模式 MUST 继续返回本班结果
- **AND** 向量与混合模式 MUST 返回 HTTP 503 与明确错误

### Requirement: 有证据的简短回答

系统 MUST 仅基于本班检索到的切片调用课程对话模型生成简短回答，引用编号 MUST 与返回的来源一一对应。无候选切片时 MUST 明确告知未找到且 MUST NOT 调用对话模型。

#### Scenario: 有命中时回答引用

- **WHEN** 本班用户提出能命中本班材料的问题
- **THEN** 系统 MUST 返回简短回答和编号一致的 citations
- **AND** citations MUST 仅链接本班材料

#### Scenario: 没有依据时不生成

- **WHEN** 过滤后没有候选切片
- **THEN** 系统 MUST 返回 HTTP 200、固定文本“资料中未找到相关内容”及空 citations
- **AND** 系统 MUST NOT 调用对话模型
