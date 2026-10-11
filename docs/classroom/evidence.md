# 截图采集与验证记录

上传文件和文字答案统一见[提交材料](提交材料/README.md)，具体要求见[课程与课堂派要求](requirements.md)。本页记录截图的来源和验证过程。

## 2026-10-11 运行截图记录

十张提交截图来自 CLab 独立测试容器：远端 `127.0.0.1:18081` 经 SSH 隧道访问，数据库、上传目录及 Qdrant 集合与原服务隔离。采集时，原 8080 服务尚未部署 Bearer 改动；这是当时的部署记录。

测试使用三个公开测试账号和测试密码，材料为种子样例及 [A 班合成科学材料](fixtures/A班-合成科学材料.md)。教师通过上传接口创建材料 ID 3，向量索引状态为 ready。课程网关实际生成嵌入和回答：问题“磁铁能吸木块吗？”，回答“不能，磁铁不能吸引木块[1]。”。点击引用打开 ID 3 的真实切片并高亮正文。

教师首页、AI 回答、来源高亮和 B 班学生首页是页面截图；登录载荷、响应、响应头、Cookie、Bearer 和未授权下载是 Chrome Network 的实际请求截图。桌面原图为 3840 × 1908，查看字段时可放大。

请求完成后，先撤销测试 JWT/session，核实有效会话数为 0，再暂存原图并遮盖认证值。接口、状态码、身份字段、Bearer 方案和 Cookie 属性保留。仓库只保存脱敏图；请求参数里的密码是隔离环境的公开测试值。

未授权下载图记录无有效会话时的 401。跨班下载 404 由自动化测试验证。取图完成后清理四份临时认证原图、停止测试容器；当时原应用报告 healthy，Qdrant 仍运行。该记录不代表后来部署状态。

当次验证结果：

- pytest 51 项通过，覆盖 JWT 签名、期限、issuer/audience、必需 claims、subject 绑定、登出撤销、无 Cookie 请求、非法 Bearer 不回退，以及角色和班级拒绝路径。
- 浏览器验证教师登录、Bearer 材料请求、Cookie 直接 API、下载 401、B 班列表，以及退出后页面跳转登录。
- AI 回答和原文溯源来自真实服务与实际点击。
- OpenSpec strict、JavaScript 语法、Git 空白和文件清单通过检查。

## 补充证据

[B 班学生首页](../evidence/classroom/0923/07-student-b-home.jpg)显示学生无上传入口，列表仅有 B 班材料。第三课交叉验收截图位于 `docs/evidence/classroom/0923/peer-verification/`，过程见[第三课验收记录](../week03-verification.md)。

报告的 [HTML 预览](../evidence/classroom/0930/04-report-html-preview.png)和 [PDF 首页](../evidence/classroom/0930/05-report-pdf-first-page.png)记录导出结果，完整记录见[报告目录](0930/README.md)。仓库组织验证截图保存在 `docs/evidence/repository/`。

## 2026-10-12 文档整理验证

- 本地 pytest 65 项通过，包含提交材料同步脚本的 14 项测试。
- 三份正式规格通过 OpenSpec strict，Bearer 变更完成归档。
- 提交材料核对通过：10 张截图、1 份 PDF 副本与原件一致，5 份文字答案原位保留。
- 本地 Markdown 链接无失效文件路径；提交索引实际渲染无横向溢出，[验证截图](../evidence/repository/document-organization.png)随改动保存。

本次验证针对本地仓库，未重新部署 CLab。

## 补取方法

在独立验收环境部署。使用本地服务时，从仓库根目录执行 `python -m scripts.evidence_server --data-dir /absolute/new/temp-directory`，指定新目录。脚本生成独立密钥、数据库和随机 Qdrant 集合，只监听 loopback；AI 截图需要真实网关配置。

认证截图先完成请求、撤销测试会话，再将原图暂存在仓库外并脱敏。`scripts/redact_evidence.py` 依赖 Pillow 10.1+，遮盖坐标采用原图像素的 left,top,right,bottom。检查脱敏结果后保存原件，用 `python3 scripts/prepare_classroom_submission.py` 同步提交副本，再运行 `--check` 核对。
