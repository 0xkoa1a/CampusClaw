# 实施与验证

- [x] 1. 实现 JWT 签发和固定 claims 校验；验证三账号登录、错误密码、未知模式、签名/期限/issuer/audience/必需 claims 和 subject 绑定。
- [x] 2. 复用服务端权限、班级过滤和 session 撤销；验证学生上传 403、跨班 404、无 Cookie Bearer 请求、非法 Bearer 不回退、旧 JWT/Cookie 重放 401。
- [x] 3. 实现浏览器 JSON 登录和 API helper；浏览器验证实际 Authorization 请求、退出清理和 Cookie 导航兼容，运行原有 pytest。
- [x] 4. 归档十项课堂派原文、截止时间与示例说明；逐条核对原页面，区分截图、分析、仓库地址和 PDF。
- [x] 5. 保存真实教师首页、登录载荷/响应/全部响应头、Cookie 身份、Bearer、未授权下载、直接 API 和 AI 引用截图；逐图检查可读性、身份、状态码和脱敏。
- [x] 6. 完成 OpenSpec strict 校验、git diff --check、截图索引及秘密检查，再本地 commit；未经用户授权不 push 或提交课堂派。

验证记录见 `docs/classroom/evidence.md`。pytest 51 项通过；十张截图包含实际课程网关问答，认证值在测试会话撤销后遮盖。0930 课后 PDF 不属于本次实施范围，留档中明确待办。
