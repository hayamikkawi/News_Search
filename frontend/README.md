# GlobalSearch Frontend

Sentiment-aware news search engine frontend interface

## 📁 Project Structure

```
frontend/
├── GlobalSearch.html       # Main HTML file
├── css/
│   └── styles.css         # Custom styles
├── js/
│   └── app.js             # Application JavaScript logic
└── README.md              # Project documentation
```

## 🎯 Architecture Overview

### Code Separation Benefits

The project has completely separated HTML, CSS, and JavaScript code:

1. **HTML** (`GlobalSearch.html`) - Only responsible for page structure and content
2. **CSS** (`css/styles.css`) - All custom styles
3. **JavaScript** (`js/app.js`) - All interaction logic and functionality

### Main Feature Modules

`js/app.js` contains the following modular features:

#### 1. Modal Management
- `initSummaryModal()` - AI smart summary modal
- `initNewsDetailModal()` - News detail modal

#### 2. Chart Visualization
- `initMiniChart()` - Sidebar mini chart
- `initModalChart()` - Modal radar chart

#### 3. Filter Functionality
- `initDateFilter()` - Date range filter
- `initSentimentFilter()` - Sentiment filter
- `initApplyFilters()` - Apply all filters

#### 4. Search Modes
- `initSearchModeToggle()` - Toggle between free text/boolean search
- `initBooleanSearch()` - Boolean search builder
- `createRuleRow()` - Create search rules
- `updateQueryPreview()` - Real-time query preview

## 🚀 Local Development

### Quick Start Scripts

Two PowerShell scripts are provided in the `frontend/` directory for easy local development:

#### 1. Start Backend Server

Run this script first to start the FastAPI backend:

```powershell
.\start-backend.ps1
```

This will:
- Configure Python path (`PYTHONPATH`)
- Check `.env` configuration
- Start backend at `http://localhost:8000`

#### 2. Start Frontend Server

In a **new PowerShell window**, run:

```powershell
.\start-frontend.ps1
```

This will:
- Start HTTP server at `http://localhost:3000`
- Serve the frontend application

#### 3. Access the Application

Open your browser and visit:
```
http://localhost:3000/GlobalSearch.html
```

### Manual Start (Alternative)

If you prefer manual commands:

**Backend (Terminal 1):**
```powershell
cd d:\web-searcher\IR
$env:PYTHONPATH="d:\web-searcher"
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Frontend (Terminal 2):**
```powershell
cd d:\web-searcher\frontend
python -m http.server 3000
```

### Verify Services

Test backend API:
```powershell
# Health check
Invoke-RestMethod "http://localhost:8000/health"

# Get latest news
Invoke-RestMethod "http://localhost:8000/news/latest?limit=5"

# Search test
Invoke-RestMethod "http://localhost:8000/search?query=news&query_type=FreeText&limit=10"
```

### Configuration

Backend configuration is in `d:\web-searcher\.env`:
```dotenv
DB_HOST=34.39.58.249
DB_PORT=3306
DB_USER=ttds_app
DB_PASSWORD=ttds#123
DB_NAME=ttds_search_engine
INDEX_BASE_DIR=d:/web-searcher/indexer/output
FRONTEND_ORIGIN=http://localhost:3000
```

---

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

#### 5. Utility Functions
- `setElementText()` - Safely set element text
- `setElementAttribute()` - Safely set element attributes
