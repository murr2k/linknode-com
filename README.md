# Linknode Energy Monitor

A real-time energy monitoring dashboard that tracks power consumption using Eagle-200 smart meter data. Built with modern web technologies, comprehensive testing, enhanced security, and deployed on Fly.io.

![Playwright](https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=playwright&logoColor=white)
![Fly.io](https://img.shields.io/badge/Fly.io-8B5CF6?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdOb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEyIDJDNi40OCAyIDIgNi40OCAyIDEyUzYuNDggMjIgMTIgMjJTMjIgMTcuNTIgMjIgMTJTMTcuNTIgMiAxMiAyWk0xMiAyMEMxMiAyMCAxMiAyMCAxMiAyMFoiIGZpbGw9IndoaXRlIi8+Cjwvc3ZnPg==&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Security](https://img.shields.io/badge/Security-Enhanced-green?style=for-the-badge&logo=shield&logoColor=white)

## 🚀 Live Demo

**Production URLs**:
- **Main Site**: [https://linknode.com](https://linknode.com)
- **Direct Fly URL**: https://linknode-web.fly.dev
- **Grafana Dashboard**: https://linknode-grafana.fly.dev
- **Eagle Monitor API**: https://linknode-eagle-monitor.fly.dev/api/stats

### Current Status

✅ **All systems operational** | 🔖 **Version: v1.1.0-security** | 🔒 **Security Enhanced**

This project features:
- Comprehensive E2E testing with Playwright (3 phases, 30+ test scenarios)
- Regression testing baseline established for quality assurance
- Automated CI/CD with GitHub Actions and security scanning
- Real-time power monitoring with Eagle-200 integration
- Professional UI with dark theme and responsive design
- Enhanced security with CSP headers, API authentication, and rate limiting
- Security monitoring and automated vulnerability scanning

## 📋 Features

- **Modern Interactive Web Interface**: 
  - Animated gradients and floating particles
  - Live power consumption widget with real-time updates
  - Embedded Grafana dashboard (no login required!)
  - API status indicators for monitoring services
  - Real-time pod/connection counter
- **Cloud Native on Fly.io** (Migrated from Kubernetes):
  - Simplified deployment with fly.toml configurations
  - Global edge network deployment
  - Built-in SSL/TLS termination
  - Automatic health checks and restarts
  - Easy secrets management
  - Legacy Kubernetes configs archived in k8s-archive-*
- **Real-time Power Monitoring**:
  - Eagle-200 smart meter integration (XML format)
  - Live power consumption dashboard (Grafana)
  - Public dashboard access (no authentication needed)
  - Time-series data storage (InfluxDB)
  - XML data ingestion endpoint
  - Automatic dashboard updates via CI/CD
  - Returns zero values when no real data available
- **Secure Access Options**: 
  - SSH tunnel access for development
  - NodePort for cost-effective public access
  - LoadBalancer support (optional)
  - Public dashboards with read-only access
- **WSL2 Compatible**: Optimized for Windows Subsystem for Linux

## 📝 Recent Updates

### Security Enhancements (2025-07-24)
- Implemented comprehensive security headers (CSP, HSTS, X-Frame-Options, etc.)
- Fixed CORS configuration - replaced wildcards with specific allowed origins
- Added API authentication with configurable API keys
- Implemented rate limiting (60 requests/minute per API key)
- Created security monitoring system with suspicious IP detection
- Added automated security scanning to CI/CD pipeline
- See [SECURITY_IMPROVEMENTS.md](./SECURITY_IMPROVEMENTS.md) for details

### Grafana Dashboard Fixes (2025-07-24)
- Fixed utility meter reading display to show "86733 kWh" instead of "87 MWh"
- Prevented Grafana's automatic unit scaling by using "none" unit with hardcoded suffix
- See [GRAFANA_METER_FIX.md](./GRAFANA_METER_FIX.md) for details

### Regression Testing Enhancement
- Visual regression tests use Playwright's built-in screenshot comparison
- Dynamic content is handled with pixel tolerance and element masking
- Fixed time ranges prevent false positives from changing data

### Known Issues
- Grafana frontend loading error: "Invalid language tag: en-US@posix"
- Backend rendering plugin not available (shows error in screenshots)
- See [GRAFANA_BLACKOUT_SOLUTION.md](./GRAFANA_BLACKOUT_SOLUTION.md) for investigation details

## 🤖 Claude Flow Development

This project is optimized for development with [claude-flow](https://github.com/ruvnet/claude-flow). State files are maintained for seamless session continuity.

### Resume Development

**General development session:**
```bash
claude-flow --project linknode \
  --context "Resume development of energy monitoring app with established regression baseline. Check CLAUDE_FLOW_STATE.md for full context. Website live at https://linknode.com" \
  --tools git,bash,web \
  --model opus-4
```

**Comprehensive session with status check:**
```bash
claude-flow --project linknode \
  --context "Continue linknode.com development. Regression baseline established (v1.0.0-baseline). All tests passing. Review CLAUDE_FLOW_STATE.md and .claude/PROJECT_CONTEXT.md for details." \
  --task "Check current deployment status and run baseline comparison" \
  --tools git,bash,web,grep,read,write \
  --model opus-4 \
  --verbose
```

### Task-Specific Sessions

**Performance Optimization:**
```bash
claude-flow --project linknode \
  --context "Optimize linknode.com performance. Baseline FCP: 148ms. See test-baselines/baseline.json" \
  --task "Analyze and improve Core Web Vitals" \
  --tools all \
  --model opus-4
```

**Feature Development:**
```bash
claude-flow --project linknode \
  --context "Add new features to linknode.com. Run regression tests after changes" \
  --task "Implement historical data visualization" \
  --tools all \
  --model opus-4
```

**Testing/Maintenance:**
```bash
claude-flow --project linknode \
  --context "Maintenance session for linknode.com" \
  --task "Run npm run baseline:compare and update baselines if needed" \
  --tools git,bash,read,write \
  --model opus-4
```

### State Files

- `CLAUDE_FLOW_STATE.md` - Comprehensive session history and project state
- `.claude/PROJECT_CONTEXT.md` - Quick reference and key commands
- `test-baselines/` - Regression testing baselines (visual, performance, API)

## 🛠️ Prerequisites

- Node.js 20+
- npm or yarn
- Fly.io CLI (`flyctl`)
- Git
- Playwright (for testing)

## 📦 Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/murr2k/rackspace-k8s-demo.git
   cd rackspace-k8s-demo
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run tests**
   ```bash
   npm test                    # Run all tests
   npm run baseline:compare    # Compare against baseline
   ```

4. **Deploy to Fly.io**
   ```bash
   # Deployment is automated via GitHub Actions
   git push origin main
   
   # Or manual deployment:
   cd fly/web && flyctl deploy
   ```

5. **Access the application**
   - Production: https://linknode.com
   - Grafana: https://linknode-grafana.fly.dev

## 📁 Project Structure

```
rackspace/
├── fly/                          # Fly.io service configurations
│   ├── web/                      # Main website (nginx)
│   │   ├── index.html           # Interactive dashboard
│   │   ├── nginx.conf           # Web server config
│   │   └── Dockerfile           # Container definition
│   ├── eagle-monitor/            # Power monitoring API
│   │   ├── server.js            # Node.js API server
│   │   └── Dockerfile           # Container definition
│   ├── grafana/                  # Metrics dashboard
│   │   └── provisioning/        # Dashboard configs
│   └── influxdb/                 # Time series database
│       └── Dockerfile           # Container definition
├── e2e/                          # E2E test suite
│   ├── tests/                    # Test specifications
│   │   ├── regression/           # Regression tests
│   │   ├── visual/               # Visual tests
│   │   └── performance/          # Performance tests
│   ├── pages/                    # Page object models
│   ├── utils/                    # Test utilities
│   └── reporters/                # Custom reporters
├── scripts/                      # Utility scripts
│   ├── capture-baseline.ts       # Baseline capture
│   └── compare-baseline.ts       # Baseline comparison
├── test-baselines/               # Regression baselines
│   ├── visual/                   # Screenshot baselines
│   └── baseline.json             # Performance/feature baseline
├── .github/workflows/            # CI/CD pipelines
│   ├── deploy-fly.yml           # Main deployment
│   ├── e2e-tests.yml            # E2E test suite
│   ├── e2e-tests-phase3.yml     # Advanced tests
│   └── regression-tests.yml      # Regression testing
├── CLAUDE_FLOW_STATE.md         # Session continuity
├── .claude/PROJECT_CONTEXT.md   # Quick reference
└── README.md                    # This file
```

## 🧪 Testing

### Comprehensive Test Suite

```bash
# Run all tests
npm test

# Specific test categories
npm run test:api          # API integration tests
npm run test:visual       # Visual regression tests
npm run test:perf         # Performance tests
npm run test:a11y         # Accessibility tests
npm run test:phase3       # Advanced tests

# Regression testing
npm run baseline:capture  # Capture new baseline
npm run baseline:compare  # Compare against baseline
npm run test:regression   # Run regression suite
```

### Test Coverage

- **Phase 1**: Smoke tests (18 scenarios)
- **Phase 2**: API mocking, visual regression, performance, accessibility
- **Phase 3**: Advanced visual and performance profiling
- **Regression**: Baseline comparison with tolerances

## 🚀 Deployment

### Automated Deployment

Push to main branch triggers automatic deployment:

```bash
git push origin main
```

### Manual Deployment

Deploy individual services:

```bash
cd fly/web && flyctl deploy
cd fly/eagle-monitor && flyctl deploy
cd fly/grafana && flyctl deploy
cd fly/influxdb && flyctl deploy
```

### Environment Variables

Required secrets in GitHub:
- `FLY_API_TOKEN` - Fly.io deployment token
- `INFLUXDB_TOKEN` - InfluxDB authentication
- `EAGLE_IP` - Eagle-200 device IP address
- `EAGLE_API_KEY` - API authentication key for Eagle monitor
- `ADMIN_API_KEY` - Admin key for security monitoring (optional)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Murray Kopit**
- GitHub: [@murr2k](https://github.com/murr2k)
- Email: murr2k@gmail.com

## 🙏 Acknowledgments

- Built with AI-augmented development using Claude
- Deployed on [Fly.io](https://fly.io)
- Testing with [Playwright](https://playwright.dev)
- Monitoring with [Grafana](https://grafana.com) and [InfluxDB](https://www.influxdata.com)

## 📊 Regression Testing

### Baseline Established

Version **v1.0.0-baseline** (2025-07-23) serves as the regression testing baseline:

- **Visual Baselines**: 8 screenshots (desktop, tablet, mobile, components)
- **Performance Metrics**: FCP 148ms, Total duration 86.3ms
- **Feature Validation**: All features documented and verified
- **API Contracts**: All endpoints returning 200 OK

### Running Regression Tests

```bash
# Compare current state to baseline
npm run baseline:compare

# Run full regression suite
npm run test:regression

# Update baseline after intentional changes
npm run baseline:capture
```

See [REGRESSION_TEST_CHECKLIST.md](REGRESSION_TEST_CHECKLIST.md) for pre-release validation.

## 📈 Features in Detail

### Power Monitoring
- **Real-time Updates**: Power consumption refreshes every 5 seconds
- **Current Power**: Live wattage display with visual indicator
- **24-hour Stats**: Min/max/average power usage
- **Cost Estimation**: Daily electricity cost calculation
- **Historical Data**: Time-series graphs via Grafana

### Dashboard Components
- **Power Widget**: Current usage with color-coded status
- **API Status**: Service health indicators
- **Build Information**: Version, date, commit SHA
- **Grafana Integration**: Embedded dashboards

### Technical Stack
- **Frontend**: Vanilla JS with dark theme
- **Backend**: Python Flask Eagle Monitor API with authentication
- **Database**: InfluxDB for time-series data
- **Visualization**: Grafana dashboards
- **Hosting**: Fly.io global edge network
- **Security**: CSP headers, API auth, rate limiting, monitoring

## 🚀 CI/CD Workflows

### GitHub Actions

1. **Deploy to Fly.io** (`deploy-fly.yml`)
   - Automatic deployment on push to main
   - Builds and deploys all 4 services
   - Updates build-info.json dynamically

2. **E2E Tests** (`e2e-tests.yml`)
   - Runs on all PRs and pushes
   - Multi-browser testing (Chrome, Firefox, Safari)
   - Smoke, API, visual, performance, accessibility tests

3. **E2E Tests Phase 3** (`e2e-tests-phase3.yml`)
   - Advanced visual and performance testing
   - Multi-viewport testing (mobile to 4K)
   - Memory profiling and animation performance

4. **Regression Tests** (`regression-tests.yml`)
   - Compares against established baseline
   - Visual, performance, and feature validation
   - Automatic PR comments with results

5. **Security Scans** (`security-scan.yml`)
   - Automated security header validation
   - Dependency vulnerability scanning
   - Code security analysis with Semgrep
   - Docker image scanning with Trivy
   - Secrets detection with Gitleaks

## 📚 Documentation

- [CLAUDE_FLOW_STATE.md](CLAUDE_FLOW_STATE.md) - Session continuity and project history
- [SECURITY_IMPROVEMENTS.md](SECURITY_IMPROVEMENTS.md) - Security implementation guide
- [FLY_MIGRATION_COMPLETE.md](FLY_MIGRATION_COMPLETE.md) - Kubernetes to Fly.io migration
- [REGRESSION_TEST_CHECKLIST.md](REGRESSION_TEST_CHECKLIST.md) - Pre-release validation checklist
- [BASELINE_ESTABLISHMENT.md](BASELINE_ESTABLISHMENT.md) - Regression baseline guide
- [E2E_TESTING_README.md](E2E_TESTING_README.md) - Comprehensive testing documentation
- [E2E_PHASE2_GUIDE.md](E2E_PHASE2_GUIDE.md) - Phase 2 testing details
- [E2E_PHASE3_GUIDE.md](E2E_PHASE3_GUIDE.md) - Phase 3 advanced testing

---

🌟 If you find this demo helpful, please consider giving it a star on GitHub!
