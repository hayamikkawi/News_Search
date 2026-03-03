# GlobalSearch Frontend-Backend Integration Deployment Guide

## 📋 Completed Integration Work

### 1. Docker Compose Configuration
✅ Added `ttds-ir` service (REST API)
- Port: 8000
- Auto-connects to MySQL database
- Mounts indexer output directory
- Configured health checks

### 2. Nginx Reverse Proxy
✅ Configured API route proxy
- `/api/*` → `http://ttds-ir:8000/*`
- Added CORS headers
- Configured timeout and connection settings

### 3. Frontend API Integration
✅ Created three new files:
- `frontend/js/api-service.js` - API client service
- `frontend/js/api-integration.js` - UI integration logic
- Updated `frontend/js/app.js` - API initialization

## 🚀 Deployment Steps

### Prerequisites
- Docker and Docker Compose
- At least 4GB available memory
- Ports 80, 3306, 8000 not occupied

### 1. Prepare Directory Structure
```bash
# Create necessary directories
mkdir -p shared/indexer/input
mkdir -p shared/indexer/output
mkdir -p shared/logs
mkdir -p mysql-data
```

### 2. Start All Services
```bash
# Run in project root directory
docker-compose -f docker-compose.crawler-full.yml up -d

# View logs
docker-compose -f docker-compose.crawler-full.yml logs -f
```

### 3. Verify Service Status
```bash
# Check if all containers are running
docker ps


### 4. Test API Connection
```bash
# Health check
curl http://localhost:8000/health

# Index version
curl http://localhost:8000/index_version

# Test search (requires crawler and indexer to run first)
curl "http://localhost:8000/search?query=energy&query_type=free_text&limit=5"
```

### 5. Access Frontend
Open browser and visit: `http://localhost`

## 📊 Data Flow Diagram

```
User Browser (http://localhost)
    ↓
Nginx (ttds-ui:80)
    ├─ Static files → HTML/CSS/JS
    └─ /api/* → Reverse proxy to IR service
              ↓
         IR Service (ttds-ir:8000)
              ├─ Query index (shared/indexer/output/)
              └─ Query database (ttds-db:3306)
                    ↑
              Crawler (ttds-crawler)
                Periodically fetches RSS and stores in database
```

## 🔧 API Endpoint Documentation

### Search News
```
GET /api/search
Parameters:
  - query: Search keywords (required)
  - query_type: 'free_text' or 'boolean' (default: free_text)
  - limit: Number of results (default: 10, max: 50)
  - offset: Pagination offset (default: 0)
  - time_from: Start time (ISO format, optional)
  - time_to: End time (ISO format, optional)
```

### Get Latest News
```
GET /api/news/latest
Parameters:
  - limit: Number of results (default: 10, max: 50)
```

### Health Check
```
GET /api/health
Returns: {"ok": true, "index_version": "..."}
```

## 🎨 Frontend Features

### Auto-Integrated Features
1. **Free Text Search** - Enter text in search box and click "Explore Now"
2. **Boolean Search** - Switch to boolean mode, build query rules
3. **Date Filtering** - Click date buttons in sidebar (Today, This Week, This Month)
4. **Latest News** - Right sidebar auto-loads latest articles
5. **Real-time Results** - Search results displayed in cards in real-time

### JavaScript Module Description

#### api-service.js
- `APIClient` class: HTTP request client (with retry logic)
- `APIService` class: Encapsulates all API calls
- `apiService` instance: Global singleton for use by other modules

#### api-integration.js
- `performSearch()`: Execute search and display results
- `renderResults()`: Render search result cards
- `loadLatestNews()`: Load latest news
- `initSearchWithAPI()`: Initialize search button events

#### app.js (updated)
- Added API integration initialization calls
- Compatible with original UI interaction features

## ⚠️ Troubleshooting

### API Connection Issues
```bash
# Check IR service status
docker logs ttds_ir

# Check network connection
docker exec ttds_ui ping ttds-ir

# Restart IR service
docker-compose -f docker-compose.crawler-full.yml restart ttds-ir
```

### No Search Results
```bash
# Check if index data exists
ls -lh shared/indexer/output/

# Check if database has data
docker exec -it ttds_mysql mysql -u ttds_app -p'ttds#123' ttds_search_engine -e "SELECT COUNT(*) FROM articles;"

# View crawler logs
docker logs ttds_crawler
```

### CORS Errors
- Verify CORS headers in nginx.conf are configured correctly
- Check browser console for error messages
- Restart nginx: `docker-compose -f docker-compose.crawler-full.yml restart ttds-ui`

## 🔄 Development Mode

### Frontend Development (Hot Reload)
Frontend files are mounted as volumes; changes take effect after browser refresh:
- `frontend/js/*.js`
- `frontend/css/styles.css`
- `frontend/GlobalSearch.html`

### Backend Development
After modifying IR code, restart the service:
```bash
docker-compose -f docker-compose.crawler-full.yml restart ttds-ir
```

## 📝 Future Optimization Suggestions

1. **Pagination** - Implement "Load More" button
2. **Loading States** - Add skeleton screens and loading animations
3. **Error Messages** - Optimize user-friendly error messages
4. **Search History** - Save user search records
5. **Advanced Filtering** - Implement sentiment analysis filtering (if backend supports)
6. **Result Highlighting** - Highlight search keywords in summaries

## 🎯 Testing Checklist

- [ ] Access http://localhost and see the interface
- [ ] Free text search returns results
- [ ] Boolean search works correctly
- [ ] Date filter works properly
- [ ] Right sidebar displays latest news
- [ ] Search result cards are clickable and navigate correctly
- [ ] API health check returns 200
- [ ] No CORS errors
- [ ] Mobile responsive layout works

## 📞 Support

If you encounter issues, check:
1. Docker container logs
2. Browser console errors
3. Nginx access logs
4. IR service logs

---

**Deployment Date**: 2026-02-21  
**Version**: 1.0.0  
**Author**: Frontend Team
