import { Page, Route } from '@playwright/test';

export interface MockResponse {
  status?: number;
  headers?: Record<string, string>;
  body?: any;
  delay?: number;
  contentType?: string;
}

export interface MockEndpoint {
  url: string | RegExp;
  method?: string;
  response: MockResponse | ((request: any) => MockResponse);
}

export class APIMocker {
  private page: Page;
  private mocks: Map<string, MockEndpoint> = new Map();
  private requestLog: Array<{ url: string; method: string; body?: any; timestamp: Date }> = [];

  constructor(page: Page) {
    this.page = page;
  }

  /**
   * Register a mock endpoint
   */
  async mock(endpoint: MockEndpoint): Promise<void> {
    const key = `${endpoint.method || 'ANY'}_${endpoint.url.toString()}`;
    this.mocks.set(key, endpoint);

    await this.page.route(endpoint.url, async (route: Route, request) => {
      // Log the request
      this.requestLog.push({
        url: request.url(),
        method: request.method(),
        body: request.postData(),
        timestamp: new Date(),
      });

      // Check if method matches
      if (endpoint.method && request.method() !== endpoint.method) {
        return route.continue();
      }

      // Get response
      let response: MockResponse;
      if (typeof endpoint.response === 'function') {
        response = endpoint.response({
          url: request.url(),
          method: request.method(),
          headers: request.headers(),
          body: request.postData(),
        });
      } else {
        response = endpoint.response;
      }

      // Apply delay if specified
      if (response.delay) {
        await new Promise(resolve => setTimeout(resolve, response.delay));
      }

      // Fulfill the request
      await route.fulfill({
        status: response.status || 200,
        headers: {
          'Content-Type': response.contentType || 'application/json',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
          ...response.headers,
        },
        body: typeof response.body === 'string' 
          ? response.body 
          : JSON.stringify(response.body || {}),
      });
    });
  }

  /**
   * Clear all mocks
   */
  async clearMocks(): Promise<void> {
    await this.page.unroute('**/*');
    this.mocks.clear();
  }

  /**
   * Get request log
   */
  getRequestLog() {
    return [...this.requestLog];
  }

  /**
   * Clear request log
   */
  clearRequestLog() {
    this.requestLog = [];
  }

  /**
   * Check if a request was made
   */
  wasRequestMade(url: string | RegExp, method?: string): boolean {
    return this.requestLog.some(req => {
      const urlMatches = typeof url === 'string' 
        ? req.url.includes(url)
        : url.test(req.url);
      const methodMatches = !method || req.method === method;
      return urlMatches && methodMatches;
    });
  }

  /**
   * Get requests matching a pattern
   */
  getRequests(url: string | RegExp, method?: string) {
    return this.requestLog.filter(req => {
      const urlMatches = typeof url === 'string' 
        ? req.url.includes(url)
        : url.test(req.url);
      const methodMatches = !method || req.method === method;
      return urlMatches && methodMatches;
    });
  }
}

// Predefined mock responses for common scenarios
export const mockResponses = {
  // Successful power stats response
  powerStats: {
    success: {
      status: 200,
      body: {
        current_power: 1234.56,
        min_power: 1000.00,
        avg_power: 1150.25,
        max_power: 1500.00,
        cost: 0.15,
        timestamp: new Date().toISOString(),
        unit: 'W',
        status: 'active',
      },
    },
    noData: {
      status: 200,
      body: {
        current_power: null,
        min_power: null,
        avg_power: null,
        max_power: null,
        cost: null,
        timestamp: new Date().toISOString(),
        status: 'no_data',
      },
    },
    error: {
      status: 500,
      body: {
        error: 'Internal server error',
        message: 'Failed to fetch power data',
      },
    },
  },

  // Health check responses
  health: {
    allHealthy: {
      status: 200,
      body: {
        status: 'healthy',
        services: {
          influxdb: { status: 'up', latency: 5 },
          eagle_monitor: { status: 'up', latency: 10 },
          web_interface: { status: 'up', latency: 1 },
        },
        timestamp: new Date().toISOString(),
      },
    },
    partial: {
      status: 200,
      body: {
        status: 'degraded',
        services: {
          influxdb: { status: 'up', latency: 5 },
          eagle_monitor: { status: 'down', error: 'Connection timeout' },
          web_interface: { status: 'up', latency: 1 },
        },
        timestamp: new Date().toISOString(),
      },
    },
    allDown: {
      status: 503,
      body: {
        status: 'unhealthy',
        services: {
          influxdb: { status: 'down', error: 'Connection refused' },
          eagle_monitor: { status: 'down', error: 'Connection timeout' },
          web_interface: { status: 'down', error: 'Service unavailable' },
        },
        timestamp: new Date().toISOString(),
      },
    },
  },

  // Historical data response
  historicalData: {
    success: {
      status: 200,
      body: {
        data: Array.from({ length: 24 }, (_, i) => ({
          timestamp: new Date(Date.now() - (23 - i) * 3600000).toISOString(),
          power: 1000 + Math.random() * 500,
          cost: 0.10 + Math.random() * 0.05,
        })),
        period: '24h',
        resolution: '1h',
      },
    },
  },

  // Error scenarios
  errors: {
    unauthorized: {
      status: 401,
      body: { error: 'Unauthorized', message: 'Invalid API key' },
    },
    forbidden: {
      status: 403,
      body: { error: 'Forbidden', message: 'Access denied' },
    },
    notFound: {
      status: 404,
      body: { error: 'Not Found', message: 'Resource not found' },
    },
    rateLimit: {
      status: 429,
      headers: {
        'X-RateLimit-Limit': '100',
        'X-RateLimit-Remaining': '0',
        'X-RateLimit-Reset': String(Date.now() + 3600000),
      },
      body: { error: 'Too Many Requests', message: 'Rate limit exceeded' },
    },
    timeout: {
      delay: 35000, // Longer than typical timeout
      status: 504,
      body: { error: 'Gateway Timeout', message: 'Request timeout' },
    },
  },
};

// Helper function to create dynamic responses
export function createDynamicPowerResponse(options: {
  basePower?: number;
  variance?: number;
  trend?: 'increasing' | 'decreasing' | 'stable';
}) {
  const base = options.basePower || 1200;
  const variance = options.variance || 100;
  let lastValue = base;

  return (request: any) => {
    // Calculate new value based on trend
    let change = (Math.random() - 0.5) * variance;
    if (options.trend === 'increasing') {
      change = Math.abs(change);
    } else if (options.trend === 'decreasing') {
      change = -Math.abs(change);
    }

    lastValue = Math.max(0, lastValue + change);

    return {
      status: 200,
      body: {
        current_power: Number(lastValue.toFixed(2)),
        min_power: Number((lastValue * 0.8).toFixed(2)),
        avg_power: Number((lastValue * 0.95).toFixed(2)),
        max_power: Number((lastValue * 1.2).toFixed(2)),
        cost: Number((lastValue * 0.0001).toFixed(4)),
        timestamp: new Date().toISOString(),
      },
    };
  };
}