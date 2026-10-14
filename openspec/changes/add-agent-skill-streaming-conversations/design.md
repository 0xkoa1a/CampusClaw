# 实现设计

## 数据与权限

skills 保留原 ID 并增加 source_text、trigger_text、description、subject_text、tools_json、enabled；旧行禁用。agents 保存班级、名称、role_prompt 和 enabled，两张绑定表仅接受本班资源。conversations 固定 user_id、class_id 和 agent_id；messages 保存正文、引用、技能名和 complete/partial 状态。迁移重复执行不改变数据，班内重名明确失败。

## 回答链路

鉴权、会话归属、当前配置、技能路由、问题落库、绑定材料检索在首个事件前执行。技能按词法命中计分，同分取较小 ID。检索的 SQL 和 Qdrant 同时限制 class_id 与绑定 material_id；混合前四条再过滤学科和空正文。历史取最新六条、每条五百字，本轮问题只进入一次。角色/技能和引用约束进入系统消息，上传资料进入用户消息。

meta 先发送技能与引用，真实网关 stream=true 的增量经引用过滤后形成 delta；助手落库成功才发送 done。流开始后错误发 error，已生成内容存 partial，断连关闭上游并释放锁。每个会话非阻塞锁防止并发发送或删除；单进程四线程部署。长流不持有数据库写事务。

## 兼容与文档

第四课 search/ask 不变；只将其正式 Requirement 明确限定到旧接口。第五课无资料仍生成，非法编号在增量阶段移除。API 使用 JSON，统一 400/401/403/404/409/503；Swagger 描述由 view 的字典注解与 Flask URL map 生成。Swagger UI 5.33.2 静态资源自托管并保留许可，不持久化令牌或访问外部校验器。

## 验收与部署

自动化测试与真实网关分开留证；apitest 每接口一个脚本、直接核对测试数据库、报告忽略且秘密脱敏。隔离环境先验证再备份正式 SQLite/上传文件并更新 CLab。同伴四项验收必须是真实第二方记录；未取得则 tasks 保留未完成，不归档。
