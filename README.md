# FileDrop

轻量级安全文件分享系统 / Secure Lightweight File Sharing Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 核心特性

| 特性 | 说明 |
|------|------|
| 文件上传 | 拖拽上传，无文件大小限制 |
| 分享链接 | 支持设置有效期和下载次数限制 |
| 密码保护 | 自动生成6位数字下载密码 |
| 文件夹分享 | 多文件打包为 ZIP 一键分享 |
| 数据外置 | 数据库/上传文件与代码分离，升级零损失 |
| 安全加固 | 文件类型白名单、CORS 配置、密码强度验证 |
| 静默下载 | 浏览器直连下载，不走 JS 进度 |

---

## 快速部署

```bash
# 克隆项目
git clone <repository-url>
cd download_site

# 配置环境变量
cp .env.example .env
# 编辑 .env，修改 SECRET_KEY 为随机字符串

# 启动服务
docker-compose up -d
```

首次访问 `http://localhost:5000/setup` 初始化管理员账户。

---

## 数据持久化

所有数据存储在容器外部，升级或重建容器不会丢失数据：

| 数据 | 默认路径 | 说明 |
|------|----------|------|
| 上传文件 | `./uploads` | 可通过 `UPLOAD_PATH` 自定义 |
| 数据库 | `./instance` | 可通过 `DATA_PATH` 自定义 |

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Flask 密钥（必填，生产环境请使用随机字符串） | - |
| `PORT` | 服务端口 | `5000` |
| `UPLOAD_PATH` | 上传文件存储路径 | `./uploads` |
| `DATA_PATH` | 数据库存储路径 | `./instance` |
| `ALLOWED_ORIGINS` | CORS 允许来源，多个用逗号分隔 | `*` |
| `PUBLIC_URL` | 公网地址，用于生成分享链接 | - |

---

## 公开运营清单

- [ ] 修改 `SECRET_KEY` 为随机字符串
- [ ] 配置 `ALLOWED_ORIGINS` 限制访问来源
- [ ] 配置 `PUBLIC_URL` 为你的公网域名
- [ ] 使用反向代理 Nginx + HTTPS
- [ ] 定期备份 `./instance` 目录

---

## 项目结构

```
download_site/
├── app/
│   ├── __init__.py      # 应用工厂
│   ├── api/
│   │   ├── admin.py     # 管理接口
│   │   ├── auth.py       # 认证接口
│   │   └── download.py   # 下载接口
│   └── models/
│       └── config.py     # 配置模型
├── templates/
│   ├── admin.html       # 管理后台
│   └── download.html    # 下载页面
├── models.py             # 数据库模型
├── run.py               # 启动入口
├── docker-compose.yml   # Docker 编排
├── Dockerfile           # Docker 构建
├── .env.example         # 环境变量示例
└── requirements.txt     # 依赖清单
```

---

## API 接口

### 认证

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/setup` | POST | 初始化管理员账户 |
| `/api/auth/login` | POST | 登录 |
| `/api/auth/logout` | POST | 登出 |

### 管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/admin/upload` | POST | 上传文件 |
| `/api/admin/files` | GET | 文件列表 |
| `/api/admin/files/<id>` | DELETE | 删除文件 |
| `/api/admin/share` | POST | 生成分享链接 |
| `/api/admin/shares` | GET | 分享列表 |
| `/api/admin/shares/<id>` | DELETE | 删除分享链接 |
| `/api/admin/config` | GET/POST | 系统配置 |

### 下载

| 接口 | 方法 | 说明 |
|------|------|------|
| `/d/<token>` | GET | 下载页面 |
| `/api/download/<token>` | GET | 获取文件信息 |
| `/api/download/<token>/verify` | POST | 验证下载密码 |
| `/api/download/<token>/file` | GET | 下载文件 |

---

## 技术栈

Flask / SQLAlchemy / SQLite / Docker / Python 3.11+

---

## License

MIT
