# 第五课：解题助手与流式会话

## Why

当前系统只有本班材料检索和单次回答，教师无法配置解题引导，学生无法恢复多轮历史。第五课要求智能体配置、技能路由、限定材料检索和真实流式会话，以及 Swagger 和接口测试。

## What Changes

- 在现有学期仓增加本班智能体、技能文件管理、绑定关系、用户私有会话和持久化消息。
- 通过新的会话消息接口输出 meta、delta、done、error，读取课程网关的真实增量响应。
- 现有 /api/ask 保持无候选不调用模型；新增会话无资料仍生成、引用为空。
- 路由旁注解生成 OpenAPI，提供自托管 Swagger 和 apitest HTML 报告（报告不入 Git）。

## Impact

沿用 Flask、SQLite、Qdrant、Bearer 和 Cookie。增量迁移保留数据；Gunicorn 改为单 worker 四线程。CLab 部署前备份，隔离环境先验收。真实同伴验收完成前保留活跃 change。
