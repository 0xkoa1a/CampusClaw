# Bearer 登录与课堂派证据

## Why

课堂派 0930 token 登录任务要求截图提交实现效果，示例明确展示材料请求的 Authorization: Bearer JWT。现有系统仅支持 Cookie 会话，不能提供这项证据。用户于 2026-10-11 确认补 OpenSpec、实现和验证 Bearer 登录。

## What Changes

- API 登录可返回签名 JWT 和用户身份；浏览器登录后以 Bearer 请求材料、上传和知识检索接口。
- 保留 Cookie 对服务器渲染页面、普通下载链接和无 JavaScript 登录的支持。
- JWT 固定算法、有效期、签发者和接收方，并关联现有服务端 session；登出同时撤销 JWT 与 Cookie。角色和班级始终从数据库读取。
- 留档课堂派十项作业要求，取得实际运行截图，敏感认证值脱敏。

## Capabilities

### New Capabilities

- `bearer-auth`: 可撤销的 Bearer JWT 登录、浏览器调用及安全边界。

### Modified Capabilities

无。现有 `auth-upload` 的 Cookie 登录、权限与班级隔离约束继续成立。

## Impact

涉及认证模块、登录与公共前端脚本、API 调用、PyJWT 依赖、测试及作业证据。截图使用隔离验收环境的合成账号和材料，真实模型结果应明确标注运行环境。
