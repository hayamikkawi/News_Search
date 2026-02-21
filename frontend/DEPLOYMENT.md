# GlobalSearch 前后端集成部署指南

## 📋 已完成的集成工作

### 1. Docker Compose 配置
✅ 添加了 `ttds-ir` 服务（REST API）
- 端口: 8000
- 自动连接到 MySQL 数据库
- 挂载索引器输出目录
- 配置了健康检查

### 2. Nginx 反向代理
✅ 配置了 API 路由代理
- `/api/*` → `http://ttds-ir:8000/*`
- 添加了 CORS 头部
- 配置了超时和连接设置

### 3. 前端 API 集成
✅ 创建了三个新文件：
- `frontend/js/api-service.js` - API 客户端服务
- `frontend/js/api-integration.js` - UI 集成逻辑
- 更新了 `frontend/js/app.js` - 初始化 API 调用

## 🚀 部署步骤

### 前置要求
- Docker 和 Docker Compose
- 至少 4GB 可用内存
- 端口 80, 3306, 8000 未被占用

### 1. 准备目录结构
```bash
# 创建必要的目录
mkdir -p shared/indexer/input
mkdir -p shared/indexer/output
mkdir -p shared/logs
mkdir -p mysql-data
```

### 2. 启动所有服务
```bash
# 在项目根目录运行
docker-compose -f docker-compose.crawler-full.yml up -d

# 查看日志
docker-compose -f docker-compose.crawler-full.yml logs -f
```

### 3. 验证服务状态
```bash
# 检查所有容器是否运行
docker ps

# 应该看到以下容器:
# - ttds_mysql (数据库)
# - ttds_crawler (爬虫调度器)
# - ttds_ir (REST API)
# - ttds_ui (前端 Nginx)
```

### 4. 测试 API 连接
```bash
# 健康检查
curl http://localhost:8000/health

# 索引版本
curl http://localhost:8000/index_version

# 测试搜索 (需要等待爬虫和索引器运行后)
curl "http://localhost:8000/search?query=energy&query_type=free_text&limit=5"
```

### 5. 访问前端
打开浏览器访问: `http://localhost`

## 📊 数据流说明

```
用户浏览器 (http://localhost)
    ↓
Nginx (ttds-ui:80)
    ├─ 静态文件 → HTML/CSS/JS
    └─ /api/* → 反向代理到 IR 服务
              ↓
         IR Service (ttds-ir:8000)
              ├─ 查询索引 (shared/indexer/output/)
              └─ 查询数据库 (ttds-db:3306)
                    ↑
              Crawler (ttds-crawler)
                定期抓取RSS并存入数据库
```

## 🔧 API 端点说明

### 搜索新闻
```
GET /api/search
参数:
  - query: 搜索关键词 (必需)
  - query_type: 'free_text' 或 'boolean' (默认: free_text)
  - limit: 结果数量 (默认: 10, 最大: 50)
  - offset: 分页偏移 (默认: 0)
  - time_from: 开始时间 (ISO格式, 可选)
  - time_to: 结束时间 (ISO格式, 可选)
```

### 获取最新新闻
```
GET /api/news/latest
参数:
  - limit: 结果数量 (默认: 10, 最大: 50)
```

### 健康检查
```
GET /api/health
返回: {"ok": true, "index_version": "..."}
```

## 🎨 前端功能

### 自动集成的功能
1. **自由文本搜索** - 在搜索框输入后点击"Explore Now"
2. **布尔搜索** - 切换到布尔模式，构建查询规则
3. **日期过滤** - 点击侧边栏的日期按钮（Today, This Week, This Month）
4. **最新新闻** - 右侧边栏自动加载最新文章
5. **实时结果** - 搜索结果实时显示在卡片中

### JavaScript 模块说明

#### api-service.js
- `APIClient` 类: HTTP 请求客户端（带重试逻辑）
- `APIService` 类: 封装所有 API 调用
- `apiService` 实例: 全局单例，供其他模块使用

#### api-integration.js
- `performSearch()`: 执行搜索并显示结果
- `renderResults()`: 渲染搜索结果卡片
- `loadLatestNews()`: 加载最新新闻
- `initSearchWithAPI()`: 初始化搜索按钮事件

#### app.js (已更新)
- 添加了 API 集成初始化调用
- 兼容原有的 UI 交互功能

## ⚠️ 故障排查

### API 无法连接
```bash
# 检查 IR 服务状态
docker logs ttds_ir

# 检查网络连接
docker exec ttds_ui ping ttds-ir

# 重启 IR 服务
docker-compose -f docker-compose.crawler-full.yml restart ttds-ir
```

### 搜索无结果
```bash
# 检查是否有索引数据
ls -lh shared/indexer/output/

# 检查数据库是否有数据
docker exec -it ttds_mysql mysql -u ttds_app -p'ttds#123' ttds_search_engine -e "SELECT COUNT(*) FROM articles;"

# 查看爬虫日志
docker logs ttds_crawler
```

### CORS 错误
- 确认 nginx.conf 中的 CORS 头部配置正确
- 检查浏览器控制台的错误信息
- 重启 nginx: `docker-compose -f docker-compose.crawler-full.yml restart ttds-ui`

## 🔄 开发模式

### 前端开发（热更新）
前端文件已挂载为 volume，修改后刷新浏览器即可看到变化：
- `frontend/js/*.js`
- `frontend/css/styles.css`
- `frontend/GlobalSearch.html`

### 后端开发
修改 IR 代码后需要重启服务：
```bash
docker-compose -f docker-compose.crawler-full.yml restart ttds-ir
```

## 📝 下一步优化建议

1. **分页功能** - 实现"加载更多"按钮
2. **加载状态** - 添加骨架屏和加载动画
3. **错误提示** - 优化用户友好的错误消息
4. **搜索历史** - 保存用户搜索记录
5. **高级过滤** - 实现情感分析过滤（如果后端支持）
6. **结果高亮** - 在摘要中高亮搜索关键词

## 🎯 测试清单

- [ ] 访问 http://localhost 能看到界面
- [ ] 自由文本搜索能返回结果
- [ ] 布尔搜索功能正常
- [ ] 日期过滤器工作正常
- [ ] 右侧边栏显示最新新闻
- [ ] 搜索结果卡片可点击跳转
- [ ] API 健康检查返回 200
- [ ] 无 CORS 错误
- [ ] 移动端响应式布局正常

## 📞 支持

如有问题，请检查：
1. Docker 容器日志
2. 浏览器控制台错误
3. Nginx 访问日志
4. IR 服务日志

---

**部署日期**: 2026-02-21  
**版本**: 1.0.0  
**作者**: Frontend Team
