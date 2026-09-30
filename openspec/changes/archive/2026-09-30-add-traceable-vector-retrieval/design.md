# Design

## 数据与边界

原始正文仍保存在 `knowledge_entries`。SQLite 中的 `knowledge_chunks` 记录 UUID、材料、班级、序号、原文起止位置、正文及标题路径；`chunk_terms` 记录中文二元词与英文单词的倒排项。现有数据库启动时执行幂等增量迁移，并为历史材料生成切片。Qdrant point ID 与切片 UUID 相同，payload 仅含 `chunk_id`、`class_id`、`material_id`、`knowledge_entry_id` 和 `chunk_index`，正文不入向量库。`materials.index_status` 与 `knowledge_chunks.index_status` 表示 `pending`、`ready` 或 `failed`。

所有新接口先校验登录。班级只取服务端会话；关键词 SQL 和 Qdrant 查询都按班级过滤，向量结果回 SQLite 后再次核对班级及 point ID。教师重建索引只能操作本班材料，学生得到 403，跨班 ID 与不存在 ID 同样返回 404。

## 切分与重建

默认自动切分上限 800 字、重叠 80 字，优先在空行、换行或句号边界断开。支持自定义分隔符和按 Markdown 标题分章；上限 100–2000 字，重叠不超过上限的 50%。切片记录原文偏移，显示结果可链接到材料详情。重建先准备新切片与向量，再替换旧索引；失败时保留原文并标记失败，允许重试。新上传先完成第三课原有的文件和全文事务，再尝试索引；模型故障不撤销上传。

## 检索与回答

`POST /api/search` 接受 `{q, mode, limit, offset}`，`mode` 为 `keyword`、`vector` 或 `hybrid`，默认 `hybrid`。关键词从 SQLite 倒排项查找，兼容两个汉字的查询；向量以课程网关的 `course-embedding` 生成 2048 维 query vector，Qdrant 使用 cosine、0.35 最低分；混合模式在各路径过滤后以 RRF(k=60) 融合。结果包含材料标题、切片序号、摘录、位置与本班来源链接。

`POST /api/ask` 接受 `{q, history}`，检索本班混合模式前 4 个切片，向 `course-chat` 发送短上下文，要求引用 `[1]` 等序号；响应同时给出与序号一一对应的 citations。无候选时返回 HTTP 200、固定文本“资料中未找到相关内容”和空 citations，不调用对话模型。Qdrant 不可用时关键词检索仍可用；向量、混合及 ask 返回 503。模型配置从环境读取，真实密钥不得提交。

## 部署与验证

Compose 加入内部 Qdrant 和持久卷，不开放公网端口；应用通过内部服务名访问。单元/接口测试使用模拟向量与对话服务；真实服务器验收使用课程网关、Qdrant 与班级账号，覆盖跨班拒绝、无依据、故障和重建。旧材料及原文在迁移和容器重建后保持可用。
