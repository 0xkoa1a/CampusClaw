# 课堂派上传、下载与身份实现分析

依据本仓库实际代码整理，供 0923 分析类作业使用。提交时配合[要求留档](requirements-2026-10-11.md)及[截图索引](evidence-2026-10-11.md)。

## 文件上传

`POST /api/materials` 由 [app/materials.py](../../app/materials.py) 实现。先识别有效用户，再要求 teacher 角色；学生直接调用接口返回 403。材料班级取自服务端当前用户，客户端 class_id 与 role 不能覆盖。

文件通过 multipart/form-data 的 file 字段上传。系统只接受最终扩展名 `.txt` 和 `.md`（不区分大小写），`.pdf`、`.docx`、图片、可执行文件和 `a.md.exe` 均不支持。前端 accept 属性只是选择器提示，后端另行校验。默认大小上限为 1 MiB，可由 MAX_UPLOAD_BYTES 配置；读取 limit+1 字节，超限返回 413。[app/knowledge.py](../../app/knowledge.py) 负责 UTF-8 解码和非空文本检查，未实现独立的 MIME、二进制字符或 PDF/DOCX 解析；不能宣称接受任意文档。

原文件名剥离路径；存储名使用随机 UUID，放到上传目录的班级子目录。原文件写入后，以 SQLite 事务插入材料、正文和切片；数据库失败回滚并清理文件。随后调用嵌入服务和 Qdrant 建索引。若向量服务失败，材料仍保留，返回 201 且 index_status=failed，教师可重建索引；这与格式校验失败（400、不入库）不同。

## 文件下载

`GET /api/materials/<id>/file` 先检查登录状态，未登录返回 401。随后查询材料并核对当前用户班级；跨班与不存在资源均返回相同 404。已登录的本班教师和学生均能下载，不要求教师角色。

只有检查通过且存储文件存在时，系统才以附件响应原文件。上传目录未挂到静态路径，用户不能绕过授权直接下载；数据库存储名和目录不返回给用户。普通下载链接使用 Cookie，API 客户端也可携带 Bearer JWT；两者共用服务端授权。

## 浏览器如何识别用户

第三课的 Cookie 流程：浏览器发送签名 session Cookie，其中只含随机 sid；[app/auth.py](../../app/auth.py) 校验签名并在 sessions 表查询有效会话，再关联 users、classes 取得用户身份。Cookie 不直接保存可被客户端修改的角色或班级权限。Cookie 配置 HttpOnly、SameSite=Lax；Secure 由 COOKIE_SECURE 控制，真实 HTTPS 部署应开启。

本次 Bearer 流程：浏览器通过 `/api/login` 的 JSON 请求指定 auth_mode=bearer，获得 HS256 JWT；token 存在当前标签页 sessionStorage，公共 API helper 自动发送 Authorization。服务端固定校验算法、签名、sub、jti、iat、exp、iss、aud，继而查询 jti 所关联的有效 session，并核对 sub；角色和班级仍从数据库读取。登出删除 session，使旧 JWT 与 Cookie 一起失效。显式无效 Bearer 返回 401，不回退到 Cookie。

Cookie 继续支持服务端页面和下载链接；没有 JavaScript 的表单登录仍可使用。token 默认 12 小时有效，与服务端会话期限一致。sessionStorage 可被同源 JavaScript 读取，因此需要防 XSS；该方案不宣称是完全无状态认证。签名密钥只从环境配置派生，截图中认证值需脱敏。

## API 暴露与部署

本仓库没有独立 Nginx。Flask 同时提供页面和 `/api/`，由 [Dockerfile](../../Dockerfile) 的 Gunicorn 在容器内 `0.0.0.0:8080` 监听。[docker-compose.yml](../../docker-compose.yml) 映射 `127.0.0.1:8080:8080`，因此宿主机本地和 SSH 隧道能访问 API，外部机器不能通过该映射直接连接。Qdrant 无宿主机端口映射，只供容器网络内部访问。

`EXPOSE 8080` 只是镜像端口元数据；真正决定宿主机可达性的是 Compose ports 绑定。浏览器可以直接打开同一来源的 `/health`、`/api/me`、`/api/materials`，已登录时 Cookie 自动发送；未登录的受保护 API 返回 401。地址栏 GET 无法直接发送 POST JSON 或自定义 Bearer 标头，这类请求由网页登录和前端调用或 API 客户端完成。

正式服务的 SSH 隧道示例为 `ssh -L 18080:127.0.0.1:8080 ubuntu@10.129.240.25`，浏览器访问 `http://127.0.0.1:18080`。本次截图使用独立测试容器及隧道端口 18081，环境边界见证据索引。
