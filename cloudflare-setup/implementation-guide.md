# Implementation Guide for True Reverse Proxy

## Option 1: Cloudflare Tunnel (Recommended - Free)

### Requirements
- A server/VM that can reach your Kubernetes cluster (can be minimal - 512MB RAM)
- The server can be anywhere (your local machine, a small VPS, or even WSL)

### Steps
1. **Install cloudflared on a server that can reach your K8s cluster:**
```bash
# On Ubuntu/Debian
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Or using Docker
docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <YOUR_TOKEN>
```

2. **Login to Cloudflare:**
```bash
cloudflared tunnel login
```

3. **Create a tunnel:**
```bash
cloudflared tunnel create linknode-tunnel
```

4. **Create config file** (`~/.cloudflared/config.yml`):
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/user/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: linknode.com
    service: http://119.9.118.22:32304
  - hostname: www.linknode.com
    service: http://119.9.118.22:32304
  - service: http_status:404
```

5. **Route DNS to tunnel:**
```bash
cloudflared tunnel route dns linknode-tunnel linknode.com
cloudflared tunnel route dns linknode-tunnel www.linknode.com
```

6. **Run the tunnel:**
```bash
cloudflared tunnel run linknode-tunnel

# Or as a service
sudo cloudflared service install
sudo systemctl start cloudflared
```

## Option 2: Free VPS with Nginx

### Free VPS Providers
- Oracle Cloud (Always Free tier - 4 ARM cores, 24GB RAM)
- Google Cloud (Free tier - e2-micro instance)
- AWS (Free tier - t2.micro for 12 months)

### Steps
1. **Create a free VPS instance**

2. **Install Nginx:**
```bash
sudo apt update
sudo apt install nginx
```

3. **Configure Nginx** (`/etc/nginx/sites-available/linknode`):
```nginx
server {
    listen 80;
    server_name linknode.com www.linknode.com;

    location / {
        proxy_pass http://119.9.118.22:32304;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

4. **Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/linknode /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

5. **Point Cloudflare to VPS IP** (not the K8s IP)

## Option 3: GitHub Pages with JavaScript Proxy

### Steps
1. **Create a GitHub repository** (e.g., `linknode-proxy`)

2. **Create `index.html`:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>Linknode</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            overflow: hidden;
        }
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        .notice {
            position: fixed;
            top: 0;
            width: 100%;
            background: #ff9800;
            color: white;
            padding: 10px;
            text-align: center;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div class="notice" id="notice">
        For security reasons, some features may not work. 
        <a href="http://119.9.118.22:32304" style="color: white;">Open directly</a>
        <button onclick="document.getElementById('notice').style.display='none'" style="float: right;">×</button>
    </div>
    <iframe src="http://119.9.118.22:32304" 
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            referrerpolicy="no-referrer">
    </iframe>
</body>
</html>
```

3. **Enable GitHub Pages** in repository settings

4. **Add custom domain** in GitHub Pages settings

## Option 4: Run Cloudflared on WSL (Easiest for Testing)

Since you're already using WSL, this is the quickest option:

### Steps
1. **Download cloudflared in WSL:**
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
```

2. **Quick tunnel (no config needed):**
```bash
# This will give you a random subdomain
cloudflared tunnel --url http://119.9.118.22:32304

# For custom domain, follow Option 1 steps
```

## Which Option Should You Choose?

1. **For permanent solution**: Option 1 (Cloudflare Tunnel) on a small VPS
2. **For immediate testing**: Option 4 (Cloudflared on WSL)
3. **For full control**: Option 2 (VPS with Nginx)
4. **For simple embed**: Option 3 (GitHub Pages)

The tunnel options (1 & 4) are best because:
- True reverse proxy (URL stays as linknode.com)
- HTTPS automatically handled
- No need to expose your K8s cluster directly
- Works with Cloudflare's security features