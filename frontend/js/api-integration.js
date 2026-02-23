// GlobalSearch - API Integration Module
// This file contains functions to integrate backend API with the UI

/**
 * Display loading state
 */
function showLoading(message = 'Searching...') {
  const resultsContainer = document.querySelector('.grid.gap-6');
  if (!resultsContainer) return;
  
  resultsContainer.innerHTML = `
    <div class="col-span-full flex flex-col items-center justify-center py-20">
      <div class="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 mb-4"></div>
      <p class="text-slate-600 text-lg font-semibold">${message}</p>
    </div>
  `;
}

/**
 * Display error message
 */
function showError(message) {
  const resultsContainer = document.querySelector('.grid.gap-6');
  if (!resultsContainer) return;
  
  resultsContainer.innerHTML = `
    <div class="col-span-full">
      <div class="bg-red-50 border-l-4 border-red-500 rounded-lg p-6">
        <div class="flex items-center">
          <span class="iconify text-red-500 w-8 h-8 mr-4" data-icon="heroicons:exclamation-triangle"></span>
          <div>
            <h3 class="text-red-800 font-bold text-lg mb-1">Search Error</h3>
            <p class="text-red-700">${message}</p>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * Display empty results
 */
function showEmptyResults(query) {
  const resultsContainer = document.querySelector('.grid.gap-6');
  if (!resultsContainer) return;
  
  resultsContainer.innerHTML = `
    <div class="col-span-full">
      <div class="bg-slate-50 border-2 border-dashed border-slate-300 rounded-xl p-12 text-center">
        <span class="iconify text-slate-400 w-20 h-20 mx-auto mb-4" data-icon="heroicons:magnifying-glass"></span>
        <h3 class="text-slate-700 font-bold text-xl mb-2">No Results Found</h3>
        <p class="text-slate-500">No articles found for "<strong>${query}</strong>"</p>
        <p class="text-slate-400 text-sm mt-2">Try adjusting your search terms or filters</p>
      </div>
    </div>
  `;
}

/**
 * Format date for display
 */
function formatDate(dateString) {
  if (!dateString) return 'Unknown date';
  
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  } catch (e) {
    return dateString;
  }
}

/**
 * Truncate text to specified length
 */
function truncateText(text, maxLength = 150) {
  if (!text || text.length <= maxLength) return text || '';
  return text.substring(0, maxLength) + '...';
}

/**
 * Extract domain from URL
 */
function extractDomain(url) {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch (e) {
    return 'Unknown source';
  }
}

/**
 * Render search results
 */
function renderResults(results) {
  const resultsContainer = document.querySelector('.grid.gap-6');
  if (!resultsContainer) return;
  
  if (!results || results.length === 0) {
    return;
  }

  const html = results.map((article, index) => {
    const domain = extractDomain(article.url || '');
    const formattedDate = formatDate(article.time);
    const headline = article.headline || 'Untitled Article';
    const url = article.url || '#';
    const id = article.id || index;
    
    return `
      <article class="bg-white rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-100 group">
        <div class="p-6">
          <!-- Header -->
          <div class="flex items-start justify-between mb-4">
            <span class="text-xs font-bold text-indigo-600 uppercase tracking-widest bg-indigo-50 px-3 py-1 rounded-full">
              ${domain}
            </span>
            <span class="text-xs text-slate-400">${formattedDate}</span>
          </div>
          
          <!-- Title -->
          <h3 class="text-xl font-bold text-slate-900 mb-3 group-hover:text-indigo-600 transition-colors leading-tight">
            <a href="${url}" target="_blank" rel="noopener" class="news-title-link">
              ${headline}
            </a>
          </h3>
          
          <!-- Footer -->
          <div class="flex items-center justify-between pt-4 border-t border-slate-100">
            <a href="${url}" target="_blank" rel="noopener" 
               class="text-sm font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1">
              <span>Read Article</span>
              <span class="iconify" data-icon="heroicons:arrow-right"></span>
            </a>
          </div>
        </div>
      </article>
    `;
  }).join('');
  
  resultsContainer.innerHTML = html;
}

/**
 * Perform search based on current mode
 */
async function performSearch(query, queryType = 'free_text', filters = {}) {
  if (!query || query.trim().length === 0) {
    showError('Please enter a search query');
    return;
  }

  try {
    showLoading('Searching for articles...');
    
    // Prepare search parameters
    const searchParams = {
      query: query.trim(),
      query_type: queryType,
      limit: filters.limit || 20,
      offset: filters.offset || 0,
    };

    // Add date filters if present
    if (filters.time_from) {
      searchParams.time_from = filters.time_from;
    }
    if (filters.time_to) {
      searchParams.time_to = filters.time_to;
    }

    console.log('Search params:', searchParams);

    // Call API
    const response = await apiService.search(searchParams);
    
    console.log('Search results:', response);

    // Update results count
    const totalResults = response.total || 0;
    updateResultsCount(totalResults, query);

    // Render results
    if (response.results && response.results.length > 0) {
      renderResults(response.results);
    } else {
      showEmptyResults(query);
    }

    // Update pagination if needed
    if (response.has_more) {
      console.log('More results available');
      // TODO: Implement pagination UI
    }

  } catch (error) {
    console.error('Search error:', error);
    if (error instanceof APIError) {
      showError(`${error.message}`);
    } else {
      showError('Failed to connect to search service. Please try again later.');
    }
  }
}

/**
 * Update results count display
 */
function updateResultsCount(count, query) {
  // Find or create results count element
  let countElement = document.getElementById('results-count');
  if (!countElement) {
    const resultsSection = document.querySelector('.grid.gap-6');
    if (resultsSection && resultsSection.parentElement) {
      countElement = document.createElement('div');
      countElement.id = 'results-count';
      countElement.className = 'mb-4 text-slate-600 font-semibold';
      resultsSection.parentElement.insertBefore(countElement, resultsSection);
    }
  }
  
  if (countElement) {
    countElement.textContent = `Found ${count} result${count !== 1 ? 's' : ''} for "${query}"`;
  }
}

/**
 * Load latest news
 */
async function loadLatestNews(limit = 10) {
  try {
    const response = await apiService.getLatestNews(limit);
    
    if (response.results && response.results.length > 0) {
      updateLatestNewsPanel(response.results);
    }
  } catch (error) {
    console.error('Failed to load latest news:', error);
  }
}

/**
 * Update latest news panel in sidebar
 */
function updateLatestNewsPanel(articles) {
  const newsPanel = document.getElementById('latest-news-panel');
  if (!newsPanel) return;
  
  const html = articles.slice(0, 5).map(article => {
    const headline = truncateText(article.headline || 'Untitled', 80);
    const formattedDate = formatDate(article.time);
    const url = article.url || '#';
    
    return `
      <div class="p-3 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors border-b border-slate-100 last:border-0">
        <a href="${url}" target="_blank" rel="noopener" class="block">
          <h4 class="font-semibold text-sm text-slate-800 mb-1 line-clamp-2">${headline}</h4>
          <p class="text-xs text-slate-500">${formattedDate}</p>
        </a>
      </div>
    `;
  }).join('');
  
  newsPanel.innerHTML = html;
}

/**
 * Get active date filter
 */
function getActiveDateFilter() {
  const activeBtn = document.querySelector('.date-filter-btn.active');
  if (!activeBtn || !activeBtn.dataset.value) return {};
  
  const value = activeBtn.dataset.value;
  const now = new Date();
  let time_from;
  
  switch(value) {
    case 'today':
      time_from = new Date(now.setHours(0, 0, 0, 0)).toISOString();
      break;
    case 'week':
      time_from = new Date(now.setDate(now.getDate() - 7)).toISOString();
      break;
    case 'month':
      time_from = new Date(now.setMonth(now.getMonth() - 1)).toISOString();
      break;
    default:
      return {};
  }
  
  return { time_from };
}

/**
 * Initialize search button handlers with API integration
 */
function initSearchWithAPI() {
  // Free text search
  const freetextSearchBtn = document.querySelector('#freetext-search button');
  const searchInput = document.getElementById('search-input');
  
  if (freetextSearchBtn && searchInput) {
    const handleSearch = () => {
      const query = searchInput.value;
      const filters = getActiveDateFilter();
      performSearch(query, 'free_text', filters);
    };
    
    freetextSearchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') handleSearch();
    });
  }

  // Boolean search - update existing handler
  const executeBooleanBtn = document.getElementById('execute-boolean-search');
  if (executeBooleanBtn) {
    // Remove old listeners by cloning
    const newBtn = executeBooleanBtn.cloneNode(true);
    executeBooleanBtn.parentNode.replaceChild(newBtn, executeBooleanBtn);
    
    newBtn.addEventListener('click', async () => {
      const booleanRules = document.getElementById('boolean-rules');
      if (!booleanRules) return;
      
      const rules = booleanRules.querySelectorAll('.boolean-rule-row');
      let queryParts = [];
      
      rules.forEach((row, index) => {
        const operator = row.querySelector('.rule-operator')?.value;
        const keyword = row.querySelector('.rule-keyword')?.value.trim();
        
        if (keyword) {
          if (index > 0) {
            queryParts.push(operator);
          }
          queryParts.push(keyword);
        }
      });
      
      if (queryParts.length === 0) {
        showError('Please enter at least one keyword');
        return;
      }
      
      const query = queryParts.join(' ');
      const filters = getActiveDateFilter();
      await performSearch(query, 'boolean', filters);
    });
  }
}
