# murraykopit.com Website Deployment on Fly.io

## Project Overview
Host a personal website at murraykopit.com using Fly.io infrastructure.

## Prerequisites
- [ ] Fly.io account (already have)
- [ ] Domain ownership of murraykopit.com
- [ ] Decision on website type (static vs dynamic)

## Setup Steps

### 1. Create Fly.io Application
```bash
# Create project directory
mkdir ~/murraykopit-site
cd ~/murraykopit-site

# Initialize Fly app
flyctl launch --name murraykopit
```

### 2. Website Options to Consider
- **Static Site** (HTML/CSS/JS)
  - Pros: Fast, simple, secure
  - Use cases: Portfolio, blog, documentation
  - Hosting: Nginx or Caddy container

- **Dynamic Site** (Node.js, Python, etc.)
  - Pros: Interactive features, API endpoints
  - Use cases: Web apps, dynamic content
  - Examples: Next.js, Express, Flask

- **CMS-based** (WordPress, Ghost, etc.)
  - Pros: Easy content management
  - Use cases: Blogs, business sites
  - Requires: Database setup

### 3. Domain Configuration

#### Add Domain to Fly.io
```bash
# Add apex domain
flyctl certs add murraykopit.com

# Add www subdomain
flyctl certs add www.murraykopit.com
```

#### DNS Configuration Options

**Option A: A/AAAA Records**
```
Type  Name  Value
----  ----  -----
A     @     66.241.124.212
AAAA  @     2a09:8280:1::24:e2b8
A     www   66.241.124.212  
AAAA  www   2a09:8280:1::24:e2b8
```

**Option B: CNAME (if provider supports CNAME flattening)**
```
Type   Name  Value
----   ----  -----
CNAME  @     murraykopit.fly.dev
CNAME  www   murraykopit.fly.dev
```

### 4. SSL Certificate
- Fly.io automatically provisions Let's Encrypt certificates
- Certificates are issued after DNS propagation (usually within minutes)
- Check certificate status: `flyctl certs show murraykopit.com`

### 5. Example Static Site Setup

Create `Dockerfile`:
```dockerfile
FROM nginx:alpine
COPY public /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 8080
```

Create `fly.toml`:
```toml
app = "murraykopit"
primary_region = "iad"

[build]

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

### 6. Deployment
```bash
# Deploy to Fly.io
flyctl deploy

# Check app status
flyctl status

# View logs
flyctl logs
```

### 7. Monitoring & Maintenance
- Monitor with: `flyctl status`
- View metrics: `flyctl dashboard`
- Scale if needed: `flyctl scale vm shared-cpu-1x --memory 256`

## Next Steps
1. Decide on website type and technology stack
2. Prepare content and design
3. Set up local development environment
4. Configure DNS provider settings
5. Deploy and test

## Notes
- Current Fly.io apps: linknode-web, linknode-grafana, linknode-influxdb, linknode-eagle-monitor
- Consider using GitHub Actions for CI/CD
- Fly.io free tier includes 3 shared-cpu-1x VMs with 256MB RAM

## Resources
- [Fly.io Docs](https://fly.io/docs/)
- [Custom Domains Guide](https://fly.io/docs/app-guides/custom-domains-with-fly/)
- [Static Site Hosting](https://fly.io/docs/app-guides/static/)