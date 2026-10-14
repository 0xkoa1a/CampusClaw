## MODIFIED Requirements

### Requirement: 有证据的简短回答
第四课 /api/ask MUST 仅基于本班检索到的切片调用课程模型，引用编号 MUST 对应来源。无候选时 MUST 明确告知未找到且 MUST NOT 调用模型。第五课新增会话接口按照 streaming-conversations 规格执行独立行为。

#### Scenario: 有命中时回答引用
- **WHEN** /api/ask 有本班命中
- **THEN** 回答 MUST 带有效本班来源引用

#### Scenario: 没有依据时不生成
- **WHEN** /api/ask 无候选
- **THEN** MUST 返回未找到且 MUST NOT 调用模型
