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

#### 5. Utility Functions
- `setElementText()` - Safely set element text
- `setElementAttribute()` - Safely set element attributes
