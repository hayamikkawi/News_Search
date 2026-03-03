// GlobalSearch API Service
// Handles all communication with the backend REST API

/**
 * API Configuration
 */
const API_CONFIG = {
  // Base URL - points to backend server
  baseURL: '/api',
  timeout: 30000, // 30 seconds
  retries: 2,
  retryBaseDelayMs: 500,
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
    this.retryBaseDelayMs = config.retryBaseDelayMs;
  }

  async parseJsonSafely(response) {
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) return {};
    return response.json().catch(() => ({}));
  }

  shouldRetry(error) {
    if (error?.name === 'AbortError') return false;
    if (error instanceof APIError) {
      return error.status === 429 || error.status >= 500;
    }
    // Network/CORS failures are usually surfaced as TypeError in fetch
    return true;
  }

  async sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Make HTTP request with retry logic
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    let lastError;
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeout);
      const requestOptions = {
        ...options,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          ...(options.body ? { 'Content-Type': 'application/json' } : {}),
          ...options.headers,
        },
      };

      try {
        const response = await fetch(url, requestOptions);
        if (!response.ok) {
          const errorData = await this.parseJsonSafely(response);
          throw new APIError(
            errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
            response.status,
            errorData
          );
        }

        return await this.parseJsonSafely(response);
      } catch (error) {
        if (error?.name === 'AbortError') {
          lastError = new APIError('Request timeout', 408, {});
        } else {
          lastError = error;
        }

        const canRetry = attempt < this.retries && this.shouldRetry(lastError);
        if (!canRetry) {
          throw lastError;
        }

        // Exponential backoff with mild jitter to reduce synchronized retries
        const jitter = Math.floor(Math.random() * 100);
        const delay = this.retryBaseDelayMs * Math.pow(2, attempt) + jitter;
        await this.sleep(delay);
      } finally {
        clearTimeout(timeoutId);
      }
    }

    throw lastError;
  }

  /**
   * GET request
   */
  async get(endpoint, params = {}) {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value));
      }
    });
    const queryString = queryParams.toString();
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
   * Generate summary for selected result ids
   * @param {Object} params - Summary request params
   * @param {string} params.query - Query text
   * @param {number[]} params.ids - Document ids
   * @returns {Promise<Object>} Summary response
   */
  async summarize(params = {}) {
    const { query = '', ids = [] } = params;
    if (!Array.isArray(ids) || ids.length === 0) {
      throw new APIError('At least one document id is required for summary', 400, {});
    }

    return this.client.post('/summarize', {
      query,
      ids,
    });
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
