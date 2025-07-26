# Content Security Policy (CSP) Implementation Guide

## Date: 2025-07-25
## Status: Ready for Deployment

### Overview

This guide documents the enhanced Content Security Policy (CSP) implementation for linknode.com, designed to provide robust protection against XSS attacks while maintaining site functionality.

### CSP Configuration

#### Current Policy (Permissive)
The current CSP maintains compatibility with existing inline scripts and styles:

```nginx
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://linknode-grafana.fly.dev;
style-src 'self' 'unsafe-inline';
img-src 'self' data: https: blob:;
font-src 'self' data:;
connect-src 'self' https://linknode-grafana.fly.dev https://linknode-influxdb.fly.dev https://linknode-eagle-monitor.fly.dev https://tracking-protection.cdn.mozilla.net;
media-src 'none';
object-src 'none';
child-src 'self';
frame-src https://linknode-grafana.fly.dev;
worker-src 'self';
form-action 'self';
base-uri 'self';
manifest-src 'self';
upgrade-insecure-requests;
```

#### Report-Only Policy (Strict)
A stricter policy is deployed in report-only mode for testing:

```nginx
default-src 'self';
script-src 'self' https://linknode-grafana.fly.dev;
style-src 'self';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self' https://linknode-grafana.fly.dev https://linknode-influxdb.fly.dev https://linknode-eagle-monitor.fly.dev;
media-src 'none';
object-src 'none';
frame-src https://linknode-grafana.fly.dev;
base-uri 'self';
form-action 'self';
upgrade-insecure-requests;
report-uri /csp-report;
```

### Key Security Improvements

1. **Explicit Directive Coverage**: Every CSP directive is explicitly defined
2. **Restricted Sources**: Only trusted domains are whitelisted
3. **No Unsafe Eval**: Prevents string-to-code execution (except temporarily for compatibility)
4. **Frame Restrictions**: Only Grafana can be embedded
5. **Form Action Limits**: Forms can only submit to same origin
6. **Base URI Protection**: Prevents base tag injection attacks
7. **Upgrade Insecure Requests**: Forces HTTPS for all resources

### CSP Violation Reporting

A reporting endpoint has been configured at `/csp-report` to:
- Accept POST requests with CSP violation reports
- Log violations to `/var/log/nginx/csp-violations.log`
- Return 204 No Content response

### Migration Path to Stricter CSP

#### Phase 1 (Current)
- Deploy permissive CSP with 'unsafe-inline'
- Deploy strict CSP in report-only mode
- Monitor violations for 1 week

#### Phase 2 (Week 2)
- Move inline styles to external CSS files
- Add nonces or hashes for necessary inline scripts
- Test thoroughly in staging

#### Phase 3 (Week 3)
- Remove 'unsafe-inline' from script-src
- Remove 'unsafe-inline' from style-src
- Deploy strict CSP as enforcing policy

### Inline Content Requiring Attention

1. **Inline Styles** (line 32): Large `<style>` block in head
   - Solution: Move to external CSS file

2. **Inline Scripts**:
   - Particle animation (line 799)
   - Build info loader (line 1070)
   - JSON-LD structured data (line 710)
   - Solutions: Use nonces or move to external files

### Testing Instructions

1. **Deploy the CSP**:
   ```bash
   ./deploy-csp-update.sh
   ```

2. **Monitor Console for Violations**:
   - Open browser DevTools
   - Navigate the site
   - Check Console for CSP violations

3. **Check Report Logs**:
   ```bash
   fly ssh console -a linknode-web
   cat /var/log/nginx/csp-violations.log
   ```

4. **Verify Functionality**:
   - Grafana iframe loads correctly
   - API calls work
   - Styles render properly
   - Scripts execute

### Browser Compatibility

The implemented CSP is compatible with:
- Chrome 25+
- Firefox 23+
- Safari 7+
- Edge 12+
- Opera 15+

### Security Benefits

1. **XSS Protection**: Blocks inline script injection
2. **Data Injection**: Prevents unauthorized data exfiltration
3. **Clickjacking**: Combined with X-Frame-Options
4. **MITM Protection**: upgrade-insecure-requests directive

### Monitoring and Maintenance

1. **Regular Reviews**: Check CSP reports weekly
2. **Policy Updates**: Adjust based on legitimate violations
3. **Testing**: Always test in report-only mode first
4. **Documentation**: Update this guide with changes

### Troubleshooting

**Issue**: Grafana dashboard not loading
- **Solution**: Ensure frame-src includes https://linknode-grafana.fly.dev

**Issue**: API calls failing
- **Solution**: Add API domain to connect-src

**Issue**: Fonts not loading
- **Solution**: Add font domain to font-src or use data: URIs

**Issue**: Images broken
- **Solution**: Check img-src includes necessary domains

### Conclusion

The enhanced CSP provides significant security improvements while maintaining compatibility. The dual-policy approach (enforcing + report-only) allows for safe migration to stricter policies based on real-world usage data.