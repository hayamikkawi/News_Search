// GlobalSearch - API Integration Module
// This file contains functions to integrate backend API with the UI

// ========================================
// SEARCH HISTORY MANAGEMENT
// ========================================

const SEARCH_HISTORY_KEY = 'global_search_history';
const MAX_HISTORY_ITEMS = 10;

/**
 * Get search history from localStorage
 */
function getSearchHistory() {
  try {
    const history = localStorage.getItem(SEARCH_HISTORY_KEY);
    return history ? JSON.parse(history) : [];
  } catch (e) {
    console.error('Failed to load search history:', e);
    return [];
  }
}

/**
 * Save search query to history
 */
function saveToHistory(query, queryType = 'FreeText') {
  if (!query || query.trim().length === 0) return;
  
  try {
    let history = getSearchHistory();
    
    // Remove duplicate if exists
    history = history.filter(item => item.query.toLowerCase() !== query.toLowerCase());
    
    // Add new search at the beginning
    history.unshift({
      query: query.trim(),
      queryType: queryType,
      timestamp: new Date().toISOString()
    });
    
    // Keep only MAX_HISTORY_ITEMS
    history = history.slice(0, MAX_HISTORY_ITEMS);
    
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
  } catch (e) {
    console.error('Failed to save search history:', e);
  }
}

/**
 * Clear search history
 */
function clearSearchHistory() {
  try {
    localStorage.removeItem(SEARCH_HISTORY_KEY);
    updateHistoryDropdown();
  } catch (e) {
    console.error('Failed to clear search history:', e);
  }
}

/**
 * Display search history dropdown
 */
function showHistoryDropdown() {
  const dropdown = document.getElementById('search-history-dropdown');
  if (!dropdown) return;
  
  const history = getSearchHistory();
  
  if (history.length === 0) {
    dropdown.innerHTML = `
      <div class="p-4 text-center text-slate-400 text-sm">
        No search history yet
      </div>
    `;
  } else {
    const html = history.map(item => {
      const timeAgo = getTimeAgo(item.timestamp);
      const typeLabel = item.queryType === 'Bool' ? 'Boolean' : 'Free Text';
      
      return `
        <div class="p-3 hover:bg-slate-50 rounded-lg cursor-pointer flex items-center justify-between search-history-item" data-query="${escapeHtml(item.query)}" data-type="${item.queryType}">
          <div class="flex-1 min-w-0">
            <span class="text-slate-700 font-medium truncate block">${escapeHtml(item.query)}</span>
            <span class="text-xs text-slate-400">${typeLabel} · ${timeAgo}</span>
          </div>
          <span class="iconify text-slate-300 ml-2" data-icon="heroicons:clock"></span>
        </div>
      `;
    }).join('');
    
    dropdown.innerHTML = html + `
      <div class="border-t border-slate-100 mt-2 pt-2">
        <button id="clear-history-btn" class="w-full p-2 text-xs text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
          Clear History
        </button>
      </div>
    `;
    
    // Add event listeners
    dropdown.querySelectorAll('.search-history-item').forEach(item => {
      item.addEventListener('click', () => {
        const query = item.dataset.query;
        const queryType = item.dataset.type;
        
        // Set the input value
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
          searchInput.value = query;
        }
        
        // Hide dropdown
        dropdown.classList.add('hidden');
        
        // Perform search
        const filters = getActiveDateFilter();
        performSearch(query, queryType, filters);
      });
    });
    
    // Clear history button
    const clearBtn = document.getElementById('clear-history-btn');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (confirm('Clear all search history?')) {
          clearSearchHistory();
        }
      });
    }
  }
  
  dropdown.classList.remove('hidden');
}

/**
 * Hide history dropdown
 */
function hideHistoryDropdown() {
  const dropdown = document.getElementById('search-history-dropdown');
  if (dropdown) {
    dropdown.classList.add('hidden');
  }
}

/**
 * Update history dropdown (refresh content)
 */
function updateHistoryDropdown() {
  const dropdown = document.getElementById('search-history-dropdown');
  if (dropdown && !dropdown.classList.contains('hidden')) {
    showHistoryDropdown();
  }
}

/**
 * Get relative time string
 */
function getTimeAgo(timestamp) {
  const now = new Date();
  const past = new Date(timestamp);
  const diffMs = now - past;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  return past.toLocaleDateString();
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ========================================
// DISPLAY FUNCTIONS
// ========================================

/**
 * Display loading state
 */
function showLoading(message = 'Searching...') {
  const resultsContainer = document.getElementById('search-results-container');
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
  const resultsContainer = document.getElementById('search-results-container');
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
  const resultsContainer = document.getElementById('search-results-container');
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
 * Extract plain search terms from a query string (strips boolean operators, proximity syntax, quotes)
 */
function extractTerms(query) {
  if (!query) return [];
  // Remove proximity syntax like #3(word1, word2)
  let q = query.replace(/#\d+\([^)]*\)/g, ' ');
  // Remove operators and punctuation
  q = q.replace(/\b(AND NOT|OR NOT|AND|OR|NOT)\b/gi, ' ');
  q = q.replace(/["""()]/g, ' ');
  // Extract words (length >= 2)
  return [...new Set(q.match(/\b[a-zA-Z0-9]{2,}\b/g) || [])];
}

/**
 * Highlight search terms in a text string
 */
function highlightKeywords(text, query) {
  const terms = extractTerms(query);
  if (!terms.length) return escapeHtml(text);
  let escaped = escapeHtml(text);
  terms.forEach(term => {
    const re = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    escaped = escaped.replace(re, '<mark class="bg-yellow-200 text-yellow-900 rounded px-0.5 not-italic font-semibold">$1</mark>');
  });
  return escaped;
}

/**
 * Render search results
 */
function renderResults(results) {
  const resultsContainer = document.getElementById('search-results-container');
  if (!resultsContainer) {
    console.error('Search results container not found');
    return;
  }
  
  if (!results || results.length === 0) {
    resultsContainer.innerHTML = '<div class="text-center py-12 text-slate-500">No results found</div>';
    return;
  }

  const html = results.map((article, index) => {
    const domain = extractDomain(article.url || '');
    const formattedDate = formatDate(article.time);
    const headline = article.headline || 'Untitled Article';
    const url = article.url || '#';
    const rawSnippet =
      article.snippet ||
      article.summary ||
      article.description ||
      article.content ||
      '';
    const snippet = truncateText(rawSnippet, 180);
    const highlightedHeadline = highlightKeywords(headline, _currentQuery);
    const highlightedSnippet = highlightKeywords(snippet, _currentQuery);
    
    return `
      <article class="bg-white rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-100 group">
        <div class="p-4">
          <!-- Header -->
          <div class="flex items-start justify-between mb-2">
            <span class="text-xs font-bold text-indigo-600 uppercase tracking-widest bg-indigo-50 px-3 py-1 rounded-full">
              ${domain}
            </span>
            <span class="text-xs text-slate-400">${formattedDate}</span>
          </div>
          
          <!-- Title -->
          <h3 class="text-base font-bold text-slate-900 mb-0 group-hover:text-indigo-600 transition-colors leading-snug">
            <a href="${url}" target="_blank" rel="noopener" class="news-title-link">
              ${highlightedHeadline}
            </a>
          </h3>
          ${
            snippet
              ? `<p class="mt-2 text-sm text-slate-600 leading-relaxed">${highlightedSnippet}</p>`
              : ''
          }
        </div>
      </article>
    `;
  }).join('');
  
  resultsContainer.innerHTML = html;
}

// ========================================
// PAGINATION STATE
// ========================================
const PAGE_SIZE = 10;
let _currentQuery = '';
let _currentQueryType = 'FreeText';
let _currentFilters = {};
let _currentPage = 1;
let _totalResults = 0;

/**
 * Get the current search state (query + type). Used by app.js for filter re-runs.
 */
function getCurrentSearchState() {
  return { query: _currentQuery, queryType: _currentQueryType };
}

/**
 * Render pagination controls
 */
function renderPagination(total, currentPage) {
  const container = document.getElementById('pagination-container');
  if (!container) return;

  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');

  const btnBase = 'px-3 py-1.5 text-sm font-semibold rounded-lg border transition-colors';
  const btnActive = 'bg-indigo-600 text-white border-indigo-600';
  const btnInactive = 'bg-white text-slate-700 border-slate-200 hover:border-indigo-400 hover:text-indigo-600';
  const btnDisabled = 'bg-slate-50 text-slate-300 border-slate-100 cursor-not-allowed';

  // Build page window: always show first, last, current±2
  const pages = new Set([1, totalPages]);
  for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) pages.add(i);
  const sortedPages = [...pages].sort((a, b) => a - b);

  let html = '';

  // Prev
  html += `<button class="${btnBase} ${currentPage === 1 ? btnDisabled : btnInactive}" 
    ${currentPage === 1 ? 'disabled' : `onclick="goToPage(${currentPage - 1})"`}>
    <span class="iconify" data-icon="heroicons:chevron-left"></span>
  </button>`;

  let prev = 0;
  for (const p of sortedPages) {
    if (prev && p - prev > 1) {
      html += `<span class="px-1 text-slate-400 text-sm">…</span>`;
    }
    html += `<button class="${btnBase} ${p === currentPage ? btnActive : btnInactive}" onclick="goToPage(${p})">${p}</button>`;
    prev = p;
  }

  // Next
  html += `<button class="${btnBase} ${currentPage === totalPages ? btnDisabled : btnInactive}" 
    ${currentPage === totalPages ? 'disabled' : `onclick="goToPage(${currentPage + 1})"`}>
    <span class="iconify" data-icon="heroicons:chevron-right"></span>
  </button>`;

  // Page info
  html += `<span class="text-xs text-slate-400 ml-2">${currentPage} / ${totalPages} pages · ${total} results</span>`;

  container.innerHTML = html;
}

/**
 * Go to a specific page
 */
function goToPage(page) {
  _currentPage = page;
  const offset = (page - 1) * PAGE_SIZE;
  _performSearchInternal(_currentQuery, _currentQueryType, { ..._currentFilters, offset, limit: PAGE_SIZE });
  // Scroll back to results
  document.getElementById('search-results-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Perform search based on current mode
 */
async function performSearch(query, queryType = 'FreeText', filters = {}) {
  _currentQuery = query;
  _currentQueryType = queryType;
  _currentFilters = filters;
  _currentPage = 1;
  await _performSearchInternal(query, queryType, { ...filters, offset: 0, limit: PAGE_SIZE });
}

async function _performSearchInternal(query, queryType, filters = {}) {
  if (!query || query.trim().length === 0) {
    showError('Please enter a search query');
    return;
  }

  // Restore normal 3-column layout (in case we were showing home feed)
  setHomeFeedLayout(false);

  try {
    showLoading('Searching for articles...');
    
    // Prepare search parameters
    const searchParams = {
      query: query.trim(),
      query_type: queryType,
      limit: filters.limit || PAGE_SIZE,
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

    // Save to search history (on successful search)
    saveToHistory(query.trim(), queryType);

    // Update results count
    const totalResults = response.total || 0;
    _totalResults = totalResults;
    updateResultsCount(totalResults, query);

    // Render results
    if (response.results && response.results.length > 0) {
      renderResults(response.results);
    } else {
      showEmptyResults(query);
    }

    // Render pagination
    renderPagination(totalResults, _currentPage);

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
  const countElement = document.getElementById('results-count');
  
  if (countElement) {
    if (count === 0) {
      countElement.textContent = `No results found for "${query}"`;
    } else {
      countElement.textContent = `Found ${count} result${count !== 1 ? 's' : ''} for "${query}"`;
    }
  }
}

/**
 * Render home feed (latest news) into main results container
 */
function setHomeFeedLayout(active) {
  const main  = document.getElementById('search-results-section');
  const aside = main ? main.nextElementSibling : null; // right sidebar
  if (!main) return;
  if (active) {
    // Expand main to span center + right (col-span-9)
    main.classList.remove('lg:col-span-6');
    main.classList.add('lg:col-span-9');
    if (aside) aside.classList.add('hidden');
  } else {
    // Restore normal search layout
    main.classList.remove('lg:col-span-9');
    main.classList.add('lg:col-span-6');
    if (aside) aside.classList.remove('hidden');
  }
}

function renderHomeFeed(articles) {
  const container = document.getElementById('search-results-container');
  const countEl   = document.getElementById('results-count');
  const pagination = document.getElementById('pagination-container');
  if (!container) return;

  // Expand layout to col-span-9
  setHomeFeedLayout(true);

  if (countEl) countEl.innerHTML = '';
  if (pagination) pagination.classList.add('hidden');

  if (!articles || articles.length === 0) {
    container.innerHTML = '<div class="text-center py-12 text-slate-400">No articles available</div>';
    return;
  }

  const cards = articles.map(article => {
    const domain = extractDomain(article.url || '');
    const date   = formatDate(article.time);
    const title  = article.headline || 'Untitled Article';
    const url    = article.url || '#';
    return `
      <article class="bg-white rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden border border-slate-100 group">
        <div class="p-3">
          <div class="flex items-start justify-between mb-1.5">
            <span class="text-xs font-bold text-rose-600 uppercase tracking-widest bg-rose-50 px-2 py-0.5 rounded-full flex items-center gap-1">
              <span class="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse"></span>
              ${escapeHtml(domain)}
            </span>
            <span class="text-xs text-slate-400 whitespace-nowrap ml-2">${date}</span>
          </div>
          <h3 class="text-sm font-semibold text-slate-900 mb-0 group-hover:text-indigo-600 transition-colors leading-snug">
            <a href="${url}" target="_blank" rel="noopener">${escapeHtml(title)}</a>
          </h3>
        </div>
      </article>
    `;
  }).join('');

  // Header + two-column cards grid
  container.innerHTML = `
    <div class="col-span-full flex items-center gap-3 mb-2">
      <span class="w-3 h-3 bg-rose-500 rounded-full animate-pulse"></span>
      <h2 class="text-xl font-extrabold text-slate-900 tracking-tight">Live Breaking News</h2>
      <span class="text-xs text-slate-400 font-medium">Latest ${articles.length} articles</span>
    </div>
    <div class="col-span-full grid grid-cols-1 md:grid-cols-2 gap-2">
      ${cards}
    </div>
  `;
}

/**
 * Load latest news
 */
async function loadLatestNews(limit = 10) {
  try {
    const response = await apiService.getLatestNews(limit);
    
    if (response.results && response.results.length > 0) {
      renderHomeFeed(response.results);      // fill main center column
      updateLatestNewsPanel(response.results); // fill sidebar
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
    case '24h':
      time_from = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();
      break;
    case 'week':
      time_from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
      break;
    case 'month':
      time_from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
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
      performSearch(query, 'FreeText', filters);
      hideHistoryDropdown();
    };

    if (!freetextSearchBtn.dataset.boundApiSearch) {
      freetextSearchBtn.addEventListener('click', handleSearch);
      freetextSearchBtn.dataset.boundApiSearch = '1';
    }

    if (!searchInput.dataset.boundApiSearch) {
      searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          handleSearch();
        }
      });

      // Show history dropdown on focus
      searchInput.addEventListener('focus', () => {
        showHistoryDropdown();
      });
      searchInput.dataset.boundApiSearch = '1';
    }

    if (!document.body.dataset.boundHistoryOutsideClick) {
      // Hide history dropdown when clicking outside
      document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('search-history-dropdown');
        const currentInput = document.getElementById('search-input');
        if (dropdown && currentInput && !dropdown.contains(e.target) && e.target !== currentInput) {
          hideHistoryDropdown();
        }
      });
      document.body.dataset.boundHistoryOutsideClick = '1';
    }
  }

  // Boolean search
  const executeBooleanBtn = document.getElementById('execute-boolean-search');
  if (executeBooleanBtn && !executeBooleanBtn.dataset.boundApiSearch) {
    executeBooleanBtn.addEventListener('click', async () => {
      const booleanRules = document.getElementById('boolean-rules');
      if (!booleanRules) return;
      
      const rules = booleanRules.querySelectorAll('.boolean-rule-row');
      let queryParts = [];
      
      rules.forEach((row, index) => {
        const q = typeof buildRowQuery === 'function' ? buildRowQuery(row) : row.querySelector('.rule-keyword')?.value.trim();
        if (q) {
          if (index > 0) {
            const operator = row.querySelector('.rule-operator')?.value || 'AND';
            queryParts.push(operator + ' ' + q);
          } else {
            queryParts.push(q);
          }
        }
      });
      
      if (queryParts.length === 0) {
        showError('Please enter at least one keyword');
        return;
      }
      
      const query = queryParts.join(' ');
      const filters = getActiveDateFilter();
      await performSearch(query, 'Bool', filters);
    });
    executeBooleanBtn.dataset.boundApiSearch = '1';
  }
}
