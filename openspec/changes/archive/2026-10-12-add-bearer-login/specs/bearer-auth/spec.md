## ADDED Requirements

### Requirement: 签发 Bearer JWT

系统 MUST 在有效账号密码且 auth_mode=bearer 的 API 登录后返回签名 JWT、token_type、有效期和用户元数据，并保留页面会话支持。

#### Scenario: 双班账号登录

- **WHEN** 教师 A、学生 A1 或学生 B1 以有效密码进行 Bearer 登录
- **THEN** 响应 MUST 为 200，JWT MUST 能访问该用户的 /api/me 和本班材料
- **AND** 响应 MUST NOT 包含密码哈希

#### Scenario: 错误密码和未知模式

- **WHEN** 用户输入错误密码或不支持的 auth_mode
- **THEN** 系统 MUST 拒绝请求且 MUST NOT 签发 token 或新会话

### Requirement: JWT 校验与服务端授权

系统 MUST 固定 HS256 并校验签名、有效期、签发者、接收方和必需 claims；身份 MUST 从关联且有效的服务端 session 与用户记录取得。显式非法 Authorization MUST NOT 回退到 Cookie。

#### Scenario: 不合法 token

- **WHEN** 请求携带篡改、过期、错误 issuer/audience、缺失必需 claims 或无效格式的 token
- **THEN** 受保护接口 MUST 返回 401，且 MUST NOT 泄露材料
- **AND** 即使请求另有有效 Cookie 也 MUST 被拒绝

#### Scenario: 服务端角色和班级

- **WHEN** 学生 A1 携带有效 token，伪造 role=teacher 或 class_id=2 后上传或读取 B 班材料
- **THEN** 上传 MUST 返回 403，跨班材料和下载 MUST 返回 404
- **AND** 本班列表 MUST 不含 B 班材料

#### Scenario: token subject 与会话绑定

- **WHEN** 签名有效 token 的 sub 与 jti 对应会话用户不一致
- **THEN** 请求 MUST 返回 401

### Requirement: 会话撤销

系统 MUST 在登出时撤销当前 JWT 与 Cookie 所关联的服务端会话，并在服务端会话过期后拒绝 token。

#### Scenario: 登出后重放

- **WHEN** 用户登出后重放旧 JWT 或旧 Cookie
- **THEN** 受保护接口 MUST 返回 401

### Requirement: 浏览器 Bearer 调用与 Cookie 兼容

浏览器 MUST 通过 JSON 登录取得 token 并对材料、上传、检索和问答 API 附加 Bearer 请求头；普通页面与下载链接 MUST 继续支持 Cookie。退出登录 MUST 清除标签页 token。

#### Scenario: 浏览器请求证据

- **WHEN** 用户以网页登录并使用材料或知识问答
- **THEN** 实际 API 请求 MUST 带 Authorization: Bearer JWT
- **AND** 页面 MUST 显示正确身份、本班内容及问答引用

#### Scenario: 原有 Cookie 客户端

- **WHEN** 客户端未请求 Bearer 或通过无 JavaScript 的表单登录
- **THEN** 原有页面、API 与下载流程 MUST 仍可使用 Cookie
