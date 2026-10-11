# 设计与 Review

## 认证流程

`POST /api/login` 默认保留 Cookie 方式；显式 `auth_mode=bearer` 时同时返回 `access_token`、`token_type=Bearer`、有效秒数和用户元数据。JWT 使用 PyJWT，固定 HS256；签名密钥从环境 SECRET_KEY 派生用途独立的密钥。必须校验 sub、jti、iat、exp、iss、aud。

JWT 的 jti 是现有随机 session 标识，sub 是用户 ID。校验签名后仍查询有效 sessions 行并核对 sub。数据库当前用户角色和班级决定权限，JWT 不承载可覆盖权限的角色/班级字段。显式 Authorization 优先，非法 token 不回退到 Cookie。登出撤销当前认证所关联的 session。

浏览器通过 JSON 登录，将 token 存在当前标签页 sessionStorage，API helper 附加 Authorization。Cookie 继续支持页面导航和下载。没有 JavaScript 时普通表单登录有效；Cookie 登录页首次加载时清除过期的前端 token。退出登录时清除 sessionStorage。

## Review（2026-10-11，实施前）

- 不信任客户端 role/class_id；所有既有权限检查复用 g.user。
- 不自写 JWT 密码学，不根据 token 的 alg 选择算法。依据 [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html) 固定校验算法和必需 claims。
- 兼容原有部署验收脚本和 Cookie 请求；Authorization 无效时返回 401。
- 登出、过期、篡改、错误 issuer/audience、跨班、学生上传及客户端伪造身份均有测试。
- 截图只保留测试密码；会话/token 必须撤销后脱敏，真实网关密钥不进入本地仓库。

Review 结论：规格可验收，可按 tasks 实施。PDF 课后方案报告独立于截图任务，本变更只归档其提交要求。
