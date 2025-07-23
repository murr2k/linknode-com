export const testData = {
  // Expected page content
  pageContent: {
    title: 'Linknode Energy Monitor - Real-Time Power Monitoring Dashboard | IoT Energy Management',
    heading: 'Linknode Energy Monitor',
    subtitle: 'Real-Time Power Monitoring • Powered by Fly.io',
  },

  // Expected elements
  expectedElements: {
    header: 'header',
    mainHeading: 'h1',
    metricsSection: '.metrics',
    liveMetricsSection: '.live-metrics-section',
    powerWidget: '.power-widget',
    apiStatusWidget: '.api-status-widget',
    grafanaPreview: '.grafana-preview',
    footer: '.footer',
  },

  // API endpoints
  apiEndpoints: {
    stats: 'https://linknode-eagle-monitor.fly.dev/api/stats',
    health: 'https://linknode-eagle-monitor.fly.dev/health',
  },

  // Expected services
  services: [
    { name: 'InfluxDB', selector: '#influx-status' },
    { name: 'Eagle Monitor', selector: '#eagle-status' },
    { name: 'Web Interface', selector: '#web-status' },
  ],

  // Test timeouts
  timeouts: {
    pageLoad: 30000,
    apiResponse: 15000,
    elementVisible: 10000,
  }
};