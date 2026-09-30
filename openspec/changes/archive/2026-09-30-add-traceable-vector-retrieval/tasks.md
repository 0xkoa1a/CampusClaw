# Tasks

- [x] 编写并严格校验本变更规格；逐项 Review 数据边界、故障语义与验收场景。验证：`openspec validate add-traceable-vector-retrieval --strict`。
- [x] 实现 SQLite 幂等迁移、历史材料切片和三种切分策略。验证：原文不变、位置正确、重启无重复、中文短词测试。
- [x] 实现课程网关适配、私有 Qdrant 存储及上传/重建索引状态。验证：模拟模型成功与失败、point ID/payload、重试和旧索引清理测试。
- [x] 实现关键词、向量、RRF 混合检索及班级双重过滤。验证：三模式排序、阈值、伪造班级、跨班 point、Qdrant 故障测试。
- [x] 实现检索与简答 API、引用链接及材料页交互。验证：无证据不调用模型、引用编号一致、权限与可见 UI 测试。
- [x] 更新 Compose、环境模板、README 并完成本地与 CLab 验收。验证：全套 pytest、OpenSpec、Compose 持久化、真实网关端到端测试；仅测试文件入库，不提交密钥。
