# Mock Inventory for Grafana Test Suite

## Overview
This document provides a comprehensive inventory of all mocks, stubs, and test doubles used in the Grafana monitoring project test suite.

## 1. [REMOVED] Regression Blackout Mock

**This mock has been removed** as it was causing more problems than it solved:
- Interfered with legitimate testing
- Created confusion about whether Grafana was actually working
- Added unnecessary complexity to the deployment

### Better Alternatives for Visual Regression Testing:
- Use Playwright's screenshot masking for dynamic elements
- Set fixed time ranges in Grafana queries
- Mock API responses at the test level, not infrastructure level
- Use `toHaveScreenshot()` with `maxDiffPixels` tolerance for minor variations

## 2. Test Browser Automation

### Location
- **File**: `/test-grafana-display.js`
- **Test framework**: Playwright

### What it's mocking
- User interaction with the Grafana dashboard (browser automation, not true mocking)

### Purpose/Reason for mocking
- Automated screenshot capture for visual regression testing
- Verification of dashboard rendering and data display

### What real implementation would look like
- **Current**: Uses Playwright to navigate to live Grafana instance
- **Real alternative**: This is already using real browser automation; no mocking involved

## 3. Energy Value Test Data

### Location
- **File**: `/check-energy-values.py`
- **Type**: Test data scenarios (not runtime mocks)

### What it's mocking
- Various energy meter reading scenarios with hardcoded test cases

### Purpose/Reason for mocking
- Diagnose unit conversion issues (kWh vs GWh display)
- Test calculation logic with known inputs

### Test scenarios included
```python
test_cases = [
    {"name": "Normal residential daily", "delivered": 50000, "mult": 1, "div": 1000},
    {"name": "High usage", "delivered": 500000, "mult": 1, "div": 1000},
    {"name": "Wrong divisor (1)", "delivered": 50000, "mult": 1, "div": 1},
    {"name": "Large cumulative", "delivered": 50000000, "mult": 1, "div": 1000},
    {"name": "Very large hex value", "delivered": 0x12345678, "mult": 1, "div": 1000},
]
```

### What real implementation would look like
- Connect to actual Eagle energy monitor device
- Read real-time energy data from InfluxDB
- Use historical production data for testing

## 4. Anonymous Authentication Mock

### Location
- **Files**: `/grafana.ini`, `/grafana-minimal.ini`, `/fly.toml`
- **Configuration**: Anonymous authentication enabled

### What it's mocking
- Real user authentication and authorization

### Purpose/Reason for mocking
- Simplifies testing by removing authentication barriers
- Allows public access to dashboards without login
- Reduces complexity for energy monitoring use case

### Configuration details
```ini
[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Admin
```

### What real implementation would look like
- Implement proper authentication (OAuth, LDAP, or Grafana native)
- Role-based access control (RBAC)
- User management and permissions
- API key authentication for programmatic access

## 5. SQLite Database Mock

### Location
- **Configuration**: `/grafana-minimal.ini`
- **Setting**: `type = sqlite3`

### What it's mocking
- Production-grade database (PostgreSQL, MySQL)

### Purpose/Reason for mocking
- Lightweight, no external dependencies
- Simplified deployment for single-instance Grafana
- Adequate for small-scale energy monitoring

### What real implementation would look like
- PostgreSQL or MySQL database
- Proper database backups and replication
- Connection pooling and performance optimization
- Database migrations and schema management

## Summary of Mock Types

1. **UI/Visual Mocks**: [REMOVED] - Tests should handle dynamic content properly
2. **Test Data**: Hardcoded energy calculation scenarios for unit testing
3. **Authentication Mock**: Anonymous access instead of proper user management
4. **Infrastructure Mock**: SQLite instead of production database

## Recommendations for Production

1. **Replace Regression Blackout** with:
   - Grafana's built-in snapshot functionality
   - Deterministic test data at the data source level
   - Visual regression tools that can handle dynamic content

2. **Implement Real Authentication**:
   - Enable Grafana's built-in authentication
   - Configure OAuth or SAML for enterprise SSO
   - Implement API tokens for programmatic access

3. **Upgrade Database**:
   - Migrate to PostgreSQL for production use
   - Implement proper backup strategies
   - Configure high availability if needed

4. **Add Real Data Source Testing**:
   - Integration tests with actual InfluxDB instances
   - Mock data at the InfluxDB level using test buckets
   - Implement data validation and monitoring

## Notes

- No traditional code-level mocks (jest mocks, sinon stubs) were found
- The project appears to favor integration testing over unit testing
- Most "mocking" is configuration-based rather than code-based
- Visual regression tests should use proper screenshot comparison techniques with tolerances