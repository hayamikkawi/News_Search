// GlobalSearch API Service
// Handles all communication with the backend REST API

/**
 * API Configuration
 */
const API_CONFIG = {
  // Base URL - points to backend server
  baseURL: 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retries: 2,
};

/**
 * API Error class
 */
class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

/**
 * HTTP client with retry logic
 */
class APIClient {
  constructor(config) {
    this.baseURL = config.baseURL;
    this.timeout = config.timeout;
    this.retries = config.retries;
  }

  /**
   * Make HTTP request with retry logic
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    const requestOptions = {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    let lastError;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const response = await fetch(url, requestOptions);
        clearTimeout(timeoutId);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new APIError(
            errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
            response.status,
            errorData
          );
        }

        return await response.json();
      } catch (error) {
        lastError = error;
        
        // Don't retry on client errors (4xx) or abort
        if (error.name === 'AbortError' || (error.status >= 400 && error.status < 500)) {
          clearTimeout(timeoutId);
          throw error;
        }

        // Wait before retry (exponential backoff)
        if (attempt < this.retries) {
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        }
      }
    }

    clearTimeout(timeoutId);
    throw lastError;
  }

  /**
   * GET request
   */
  async get(endpoint, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    return this.request(url, { method: 'GET' });
  }

  /**
   * POST request
   */
  async post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

/**
 * API Service - Main interface for frontend
 */
class APIService {
  constructor() {
    this.client = new APIClient(API_CONFIG);
  }

  /**
   * Search news articles
   * @param {Object} params - Search parameters
   * @param {string} params.query - Search query text
   * @param {string} params.query_type - Query type: 'FreeText' or 'Bool'
   * @param {number} params.limit - Number of results per page (default: 10)
   * @param {number} params.offset - Offset for pagination (default: 0)
   * @param {string} params.time_from - Filter by start date (ISO format)
   * @param {string} params.time_to - Filter by end date (ISO format)
   * @returns {Promise<Object>} Search results
   */
  async search(params) {
    const {
      query,
      query_type = 'FreeText',
      limit = 10,
      offset = 0,
      time_from,
      time_to,
    } = params;

    if (!query || query.trim().length === 0) {
      throw new APIError('Search query cannot be empty', 400, {});
    }

    const searchParams = {
      query: query.trim(),
      query_type,
      limit,
      offset,
    };

    if (time_from) searchParams.time_from = time_from;
    if (time_to) searchParams.time_to = time_to;

    return this.client.get('/search', searchParams);
  }

  /**
   * Get latest news articles
   * @param {number} limit - Number of articles to fetch (default: 10)
   * @returns {Promise<Object>} Latest news
   */
  async getLatestNews(limit = 10) {
    return this.client.get('/news/latest', { limit });
  }

  /**
   * Health check
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    return this.client.get('/health');
  }

  /**
   * Get index version
   * @returns {Promise<Object>} Index version info
   */
  async getIndexVersion() {
    return this.client.get('/index_version');
  }
}

/**
 * Singleton instance
 */
const apiService = new APIService();

/**
 * Export for use in other modules
 */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { APIService, apiService, APIError };
}
