// GlobalSearch - Main Application JavaScript
// Separated from HTML for better maintainability

// ============================================
// Modal Management
// ============================================

/**
 * Initialize and manage the summary modal
 */
function initSummaryModal() {
  const summaryBtn = document.getElementById('summary-btn');
  const modalOverlay = document.getElementById('modal-overlay');
  const closeModal = document.getElementById('close-modal');
  const modalContent = modalOverlay?.querySelector('.bg-white');

  if (!summaryBtn || !modalOverlay || !closeModal || !modalContent) {
    console.warn('Summary modal elements not found');
    return;
  }

  summaryBtn.onclick = () => {
    modalOverlay.classList.remove('opacity-0', 'pointer-events-none');
    modalContent.classList.remove('translate-y-8');
    initModalChart();
  };

  closeModal.onclick = () => {
    modalOverlay.classList.add('opacity-0', 'pointer-events-none');
    modalContent.classList.add('translate-y-8');
  };
}

/**
 * Initialize and manage the news detail modal
 */
function initNewsDetailModal() {
  const newsDetailOverlay = document.getElementById('news-detail-overlay');
  const newsDetailContent = newsDetailOverlay?.querySelector('.bg-white');
  const closeNewsDetail = document.getElementById('close-news-detail');
  const newsTitles = document.querySelectorAll('.news-title');

  if (!newsDetailOverlay || !newsDetailContent || !closeNewsDetail) {
    console.warn('News detail modal elements not found');
    return;
  }

  // Sample full content for each news
  const newsContent = {
    '1': {
      content: `The International Energy Organization announced today that the superconducting grid project has successfully completed its first phase of grid connection in Northern Europe. This groundbreaking initiative represents a major breakthrough in clean energy transmission technology.
      
      The project utilizes advanced superconducting materials that allow electricity to flow with virtually zero resistance, reducing cross-border power transmission losses by an unprecedented 40%. This efficiency gain could save billions in energy costs annually while significantly reducing carbon emissions.
      
      Engineers working on the project report that the system has exceeded initial performance expectations. The superconducting cables, cooled to near absolute zero temperatures, have demonstrated remarkable stability even under peak load conditions.
      
      Over the next three years, the technology is expected to expand to other regions, potentially revolutionizing the global energy grid infrastructure. Energy ministers from 12 European nations have already expressed interest in adopting this technology.`,
      keypoints: [
        'First phase of superconducting grid successfully completed',
        '40% reduction in cross-border power transmission losses',
        'Near-zero resistance technology using advanced superconducting materials',
        'Expansion to other regions planned over next 3 years',
        '12 European nations interested in adopting the technology'
      ]
    },
    '2': {
      content: `IBM and Google's joint quantum computing laboratory has announced a major milestone: the Tianzhou quantum chip series has successfully completed 10,000 connectivity tests, bringing quantum computing significantly closer to practical commercialization.
      
      This achievement marks a turning point in the quantum computing industry. The Tianzhou chips demonstrate unprecedented stability and error correction capabilities, addressing one of the major obstacles to quantum computer deployment.
      
      Leading tech companies are now rushing to form specialized algorithm development teams. Traditional programming paradigms don't apply to quantum systems, requiring engineers to fundamentally rethink computational approaches.
      
      Industry experts predict that within 5 years, quantum computers could tackle problems currently impossible for classical computers, including drug discovery, climate modeling, and cryptography.`,
      keypoints: [
        '10,000 successful connectivity tests completed',
        'Major advancement in quantum chip stability',
        'Tech giants forming new algorithm development teams',
        'Programmers must learn entirely new computational paradigms',
        'Practical applications expected within 5 years'
      ]
    }
  };

  newsTitles.forEach(title => {
    title.addEventListener('click', () => {
      const id = title.dataset.id;
      const data = newsContent[id] || { content: 'Full content not available yet.', keypoints: [] };

      // Fill modal with data
      setElementText('detail-category', title.dataset.category);
      setElementText('detail-title', title.dataset.title);
      setElementText('detail-date', title.dataset.date);
      setElementAttribute('detail-image', 'src', title.dataset.image);
      setElementText('detail-content', data.content);

      // Fill key points
      const keypointsContainer = document.getElementById('detail-keypoints');
      if (keypointsContainer) {
        keypointsContainer.innerHTML = data.keypoints.map(point => `<li>• ${point}</li>`).join('');
      }

      // Reset scroll position to top
      const modalScrollContainer = newsDetailOverlay.querySelector('.overflow-y-auto');
      if (modalScrollContainer) {
        modalScrollContainer.scrollTop = 0;
      }

      // Show modal
      newsDetailOverlay.classList.remove('opacity-0', 'pointer-events-none');
      newsDetailContent.classList.remove('translate-y-8');
    });
  });

  closeNewsDetail.onclick = () => {
    newsDetailOverlay.classList.add('opacity-0', 'pointer-events-none');
    newsDetailContent.classList.add('translate-y-8');
  };

  // Close on backdrop click
  newsDetailOverlay.addEventListener('click', (e) => {
    if (e.target === newsDetailOverlay) {
      newsDetailOverlay.classList.add('opacity-0', 'pointer-events-none');
      newsDetailContent.classList.add('translate-y-8');
    }
  });
}

// ============================================
// Chart Initialization (ECharts)
// ============================================

/**
 * Initialize mini chart in sidebar
 */
function initMiniChart() {
  const chartDom = document.getElementById('mini-chart');
  if (!chartDom) {
    console.warn('mini-chart element not found');
    return;
  }
  const myChart = echarts.init(chartDom);
  const option = {
    grid: { top: 0, bottom: 0, left: 0, right: 0 },
    xAxis: { type: 'category', show: false },
    yAxis: { show: false },
    series: [{
      data: [120, 200, 150, 80, 70, 110, 130, 280, 220, 290],
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { color: 'rgba(99, 102, 241, 0.3)' },
      lineStyle: { width: 3, color: '#818cf8' }
    }]
  };
  myChart.setOption(option);
}

/**
 * Initialize modal chart (radar chart)
 */
function initModalChart() {
  setTimeout(() => {
    const chartDom = document.getElementById('summary-chart');
    if (!chartDom) {
      console.warn('summary-chart element not found');
      return;
    }
    const myChart = echarts.init(chartDom);
    const option = {
      radar: {
        indicator: [
          { name: 'Positivity', max: 100 },
          { name: 'Credibility', max: 100 },
          { name: 'Virality', max: 100 },
          { name: 'Complexity', max: 100 },
          { name: 'Impact', max: 100 }
        ],
        splitArea: { show: false },
        axisLine: { lineStyle: { color: '#e2e8f0' } }
      },
      series: [{
        type: 'radar',
        data: [
          {
            value: [85, 92, 78, 40, 88],
            name: 'Current Topic Characteristics',
            areaStyle: { color: 'rgba(79, 70, 229, 0.4)' },
            lineStyle: { color: '#4f46e5' },
            itemStyle: { color: '#4f46e5' }
          }
        ]
      }]
    };
    myChart.setOption(option);
  }, 300);
}

// ============================================
// Filter Management
// ============================================

/**
 * Initialize date filter functionality
 */
function initDateFilter() {
  const dateFilterBtns = document.querySelectorAll('.date-filter-btn');
  dateFilterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      dateFilterBtns.forEach(b => {
        b.classList.remove('bg-indigo-50', 'text-indigo-700', 'border-indigo-100', 'active');
        b.classList.add('bg-white', 'text-slate-600', 'border-slate-200');
      });
      btn.classList.add('bg-indigo-50', 'text-indigo-700', 'border-indigo-100', 'active');
      btn.classList.remove('bg-white', 'text-slate-600', 'border-slate-200');
      console.log('Selected date filter:', btn.dataset.value);
    });
  });
}

/**
 * Initialize apply filters button
 */
function initApplyFilters() {
  const applyFiltersBtn = document.getElementById('apply-filters-btn');
  if (!applyFiltersBtn) return;

  applyFiltersBtn.addEventListener('click', () => {
    // Re-run current search with updated date filter
    // Use getCurrentSearchState() to reliably get last query + type (FreeText or Bool)
    const state = typeof getCurrentSearchState === 'function' ? getCurrentSearchState() : {};
    const query = (state.query && state.query.trim())
      ? state.query.trim()
      : (() => { const el = document.getElementById('search-input'); return el ? el.value.trim() : ''; })();
    const queryType = (state.query && state.query.trim() && state.queryType)
      ? state.queryType
      : 'FreeText';

    if (!query) {
      applyFiltersBtn.textContent = 'Enter a query first';
      setTimeout(() => { applyFiltersBtn.textContent = 'Apply Filters'; }, 1500);
      return;
    }

    if (typeof getActiveDateFilter !== 'undefined' && typeof performSearch !== 'undefined') {
      const filters = getActiveDateFilter();
      performSearch(query, queryType, filters);
    }

    applyFiltersBtn.textContent = 'Filters Applied ✓';
    applyFiltersBtn.classList.add('bg-emerald-600', 'hover:bg-emerald-700');
    applyFiltersBtn.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
    setTimeout(() => {
      applyFiltersBtn.textContent = 'Apply Filters';
      applyFiltersBtn.classList.remove('bg-emerald-600', 'hover:bg-emerald-700');
      applyFiltersBtn.classList.add('bg-indigo-600', 'hover:bg-indigo-700');
    }, 2000);
  });
}

// ============================================
// Search Mode Management
// ============================================

/**
 * Initialize search mode toggle (Free Text vs Boolean)
 */
function initSearchModeToggle() {
  const modeToggleButtons = document.querySelectorAll('.mode-toggle');
  const freetextSearch = document.getElementById('freetext-search');
  const booleanSearch = document.getElementById('boolean-search');

  if (!freetextSearch || !booleanSearch) return;

  modeToggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      // Update button states
      modeToggleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Update button styles
      if (btn.id === 'mode-freetext') {
        btn.style.backgroundColor = 'white';
        btn.style.color = '#4f46e5';
        btn.style.border = 'none';

        const booleanBtn = document.getElementById('mode-boolean');
        if (booleanBtn) {
          booleanBtn.style.backgroundColor = 'rgba(255,255,255,0.2)';
          booleanBtn.style.color = 'white';
          booleanBtn.style.border = '2px solid rgba(255,255,255,0.3)';
        }

        // Show free text, hide boolean
        freetextSearch.classList.remove('hidden');
        booleanSearch.classList.add('hidden');
      } else {
        // Boolean active
        btn.style.backgroundColor = 'white';
        btn.style.color = '#4f46e5';
        btn.style.border = 'none';

        const freetextBtn = document.getElementById('mode-freetext');
        if (freetextBtn) {
          freetextBtn.style.backgroundColor = 'rgba(255,255,255,0.2)';
          freetextBtn.style.color = 'white';
          freetextBtn.style.border = '2px solid rgba(255,255,255,0.3)';
        }

        // Show boolean, hide free text
        booleanSearch.classList.remove('hidden');
        freetextSearch.classList.add('hidden');
      }
    });
  });
}

// ============================================
// Boolean Search Builder
// ============================================

/**
 * Create a new rule row for boolean search
 * @param {boolean} isFirst - Whether this is the first rule
 * @returns {HTMLElement} The created rule row element
 */
function createRuleRow(isFirst = false) {
  const row = document.createElement('div');
  row.className = 'boolean-rule-row flex flex-col gap-2 bg-white/5 p-4 rounded-2xl backdrop-blur-sm border border-white/20';

  // ── Top line: operator + type + delete + add ──
  const topLine = document.createElement('div');
  topLine.className = 'flex gap-2 items-center';

  // Logical Operator
  const operatorSelect = document.createElement('select');
  operatorSelect.className = 'rule-operator text-sm font-semibold px-3 py-2 rounded-lg border border-slate-400 cursor-pointer';
  operatorSelect.style.cssText = 'background-color:#2d3748;color:white;min-width:110px';
  operatorSelect.innerHTML = '<option value="AND">AND</option><option value="OR">OR</option><option value="AND NOT">AND NOT</option><option value="OR NOT">OR NOT</option>';
  if (isFirst) operatorSelect.style.display = 'none';

  // Search Type
  const typeSelect = document.createElement('select');
  typeSelect.className = 'rule-type text-sm font-semibold px-3 py-2 rounded-lg border border-slate-400 cursor-pointer';
  typeSelect.style.cssText = 'background-color:#2d3748;color:white;min-width:130px';
  typeSelect.innerHTML = '<option value="term">Term</option><option value="phrase">Phrase</option><option value="proximity">Proximity</option>';

  // Delete Button
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'delete-rule ml-auto px-3 py-2 bg-red-500/20 text-red-200 rounded-lg hover:bg-red-500/40 transition-colors';
  if (isFirst) deleteBtn.style.display = 'none';
  deleteBtn.innerHTML = '<span class="iconify" data-icon="heroicons:x-mark"></span>';

  // Add Button
  const addBtn = document.createElement('button');
  addBtn.className = 'add-rule px-3 py-2 bg-emerald-500/20 text-emerald-200 rounded-lg hover:bg-emerald-500/40 transition-colors';
  addBtn.innerHTML = '<span class="iconify" data-icon="heroicons:plus"></span>';

  topLine.appendChild(operatorSelect);
  topLine.appendChild(typeSelect);
  topLine.appendChild(deleteBtn);
  topLine.appendChild(addBtn);

  // ── Dynamic input area ──
  const inputArea = document.createElement('div');
  inputArea.className = 'rule-inputs flex gap-2 items-center flex-wrap';

  function mkInput(cls, placeholder, extraStyle = '') {
    const inp = document.createElement('input');
    inp.className = cls + ' px-4 py-2 rounded-lg text-slate-900 outline-none text-sm placeholder:text-slate-400';
    inp.type = 'text';
    inp.placeholder = placeholder;
    if (extraStyle) inp.style.cssText = extraStyle;
    inp.addEventListener('input', updateQueryPreview);
    return inp;
  }

  function mkLabel(text) {
    const s = document.createElement('span');
    s.className = 'text-white/60 text-xs font-semibold shrink-0';
    s.textContent = text;
    return s;
  }

  function renderInputs(type) {
    inputArea.innerHTML = '';
    if (type === 'term') {
      inputArea.appendChild(mkInput('rule-keyword flex-1', 'Enter keyword…'));
    } else if (type === 'phrase') {
      inputArea.appendChild(mkInput('rule-phrase-w1 flex-1', 'First word…'));
      inputArea.appendChild(mkLabel('+'));
      inputArea.appendChild(mkInput('rule-phrase-w2 flex-1', 'Second word…'));
      const hint = document.createElement('span');
      hint.className = 'text-white/30 text-xs w-full';
      hint.textContent = 'Matches documents where both words appear consecutively';
      inputArea.appendChild(hint);
    } else if (type === 'proximity') {
      inputArea.appendChild(mkInput('rule-prox-w1 flex-1', 'Word 1…'));
      inputArea.appendChild(mkLabel('within'));
      const nInp = document.createElement('input');
      nInp.className = 'rule-prox-n w-14 px-2 py-2 rounded-lg text-slate-900 outline-none text-sm text-center';
      nInp.type = 'number';
      nInp.min = '1'; nInp.max = '99'; nInp.value = '3';
      nInp.addEventListener('input', updateQueryPreview);
      inputArea.appendChild(nInp);
      inputArea.appendChild(mkLabel('words of'));
      inputArea.appendChild(mkInput('rule-prox-w2 flex-1', 'Word 2…'));
      const hint = document.createElement('span');
      hint.className = 'text-white/30 text-xs w-full';
      hint.textContent = 'Matches documents where Word 1 appears within N words of Word 2';
      inputArea.appendChild(hint);
    }
  }

  renderInputs('term');

  typeSelect.addEventListener('change', () => { renderInputs(typeSelect.value); updateQueryPreview(); });
  operatorSelect.addEventListener('change', updateQueryPreview);

  deleteBtn.addEventListener('click', () => {
    row.remove();
    const booleanRules = document.getElementById('boolean-rules');
    if (!booleanRules) return;
    const rows = booleanRules.querySelectorAll('.boolean-rule-row');
    if (rows.length > 0) {
      const lastAddBtn = rows[rows.length - 1].querySelector('.add-rule');
      if (lastAddBtn) lastAddBtn.style.display = 'block';
    }
    updateQueryPreview();
  });

  addBtn.addEventListener('click', () => {
    addBtn.style.display = 'none';
    const booleanRules = document.getElementById('boolean-rules');
    if (!booleanRules) return;
    booleanRules.appendChild(createRuleRow(false));
    updateQueryPreview();
  });

  row.appendChild(topLine);
  row.appendChild(inputArea);
  return row;
}

/**
 * Build query string from a single rule row
 */
function buildRowQuery(row) {
  const type = row.querySelector('.rule-type')?.value || 'term';
  if (type === 'term') {
    return row.querySelector('.rule-keyword')?.value.trim() || null;
  } else if (type === 'phrase') {
    const w1 = row.querySelector('.rule-phrase-w1')?.value.trim();
    const w2 = row.querySelector('.rule-phrase-w2')?.value.trim();
    return (w1 && w2) ? `"${w1} ${w2}"` : null;
  } else if (type === 'proximity') {
    const w1 = row.querySelector('.rule-prox-w1')?.value.trim();
    const w2 = row.querySelector('.rule-prox-w2')?.value.trim();
    const n  = row.querySelector('.rule-prox-n')?.value || '3';
    return (w1 && w2) ? `#${n}(${w1}, ${w2})` : null;
  }
  return null;
}

/**
 * Update query preview in real-time
 */
function updateQueryPreview() {
  const booleanRules = document.getElementById('boolean-rules');
  const queryPreviewText = document.getElementById('query-preview-text');
  
  if (!booleanRules || !queryPreviewText) return;

  const rules = booleanRules.querySelectorAll('.boolean-rule-row');
  if (rules.length === 0) return;

  let queryParts = [];

  rules.forEach((row, index) => {
    const q = buildRowQuery(row);
    if (q) {
      if (index > 0) {
        const op = row.querySelector('.rule-operator')?.value || 'AND';
        queryParts.push(op + ' ' + q);
      } else {
        queryParts.push(q);
      }
    }
  });

  if (queryParts.length > 0) {
    queryPreviewText.innerHTML = `<span style="color:#a0aec0">${queryParts.join(' ')}</span>`;
  } else {
    queryPreviewText.innerHTML = `<span class="text-white/40">Your boolean expression will appear here...</span>`;
  }
}

/**
 * Initialize boolean search functionality
 */
function initBooleanSearch() {
  const booleanRules = document.getElementById('boolean-rules');
  const executeBooleanBtn = document.getElementById('execute-boolean-search');
  const resetBooleanBtn = document.getElementById('reset-boolean-search');

  if (!booleanRules || !executeBooleanBtn || !resetBooleanBtn) return;

  // Keep demo search handler only when API integration is unavailable.
  if (typeof performSearch === 'undefined') {
    executeBooleanBtn.addEventListener('click', () => {
      const rules = booleanRules.querySelectorAll('.boolean-rule-row');
      let queryParts = [];
      let hasValidRule = false;

      rules.forEach((row, index) => {
        const operator = row.querySelector('.rule-operator')?.value;
        const keyword = row.querySelector('.rule-keyword')?.value.trim();
        const field = row.querySelector('.rule-field')?.value;

        if (keyword) {
          hasValidRule = true;
          let part = '';

          if (index > 0) {
            part += operator + ' ';
          }

          if (field) {
            part += `"${keyword}" (${field})`;
          } else {
            part += `"${keyword}"`;
          }

          queryParts.push(part);
        }
      });

      if (!hasValidRule) {
        alert('Please enter at least one keyword');
        return;
      }

      const finalQuery = queryParts.join(' ');
      console.log('Executing Boolean Search Query:', finalQuery);

      // Show feedback
      executeBooleanBtn.textContent = 'Searching...';
      executeBooleanBtn.disabled = true;

      setTimeout(() => {
        executeBooleanBtn.innerHTML = '<span class="iconify" data-icon="heroicons:magnifying-glass"></span> <span>Search</span>';
        executeBooleanBtn.disabled = false;
        console.log('Search Results Updated (Demo)');
      }, 1500);
    });
  }

  // Reset boolean search
  resetBooleanBtn.addEventListener('click', () => {
    booleanRules.innerHTML = '';
    booleanRules.appendChild(createRuleRow(true));
    const queryPreviewText = document.getElementById('query-preview-text');
    if (queryPreviewText) {
      queryPreviewText.innerHTML = `<span class="text-white/40">Your boolean expression will appear here...</span>`;
    }
  });

  // Initialize with first rule row
  booleanRules.appendChild(createRuleRow(true));
}

// ============================================
// Helper Functions
// ============================================

/**
 * Safely set element text content
 * @param {string} id - Element ID
 * @param {string} text - Text to set
 */
function setElementText(id, text) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = text;
  }
}

/**
 * Safely set element attribute
 * @param {string} id - Element ID
 * @param {string} attr - Attribute name
 * @param {string} value - Attribute value
 */
function setElementAttribute(id, attr, value) {
  const element = document.getElementById(id);
  if (element) {
    element.setAttribute(attr, value);
  }
}

// ============================================
// Application Initialization
// ============================================

/**
 * Initialize all application features
 */
function initApp() {
  console.log('GlobalSearch app initializing...');

  // Initialize charts
  initMiniChart();

  // Initialize modals
  initSummaryModal();
  initNewsDetailModal();

  // Initialize filters
  initDateFilter();
  initApplyFilters();

  // Initialize search modes
  initSearchModeToggle();
  initBooleanSearch();

  // Initialize API integration (if available)
  if (typeof initSearchWithAPI !== 'undefined') {
    initSearchWithAPI();
    console.log('API integration initialized');
  }

  // Load latest news (if API is available)
  if (typeof loadLatestNews !== 'undefined') {
    loadLatestNews(50);
    console.log('Loading latest news...');
  }

  console.log('GlobalSearch app initialized successfully');
}

// Start the app when DOM is fully loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  // DOM is already loaded
  initApp();
}
