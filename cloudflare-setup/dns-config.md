# DNS Configuration for Cloudflare

## 🎯 Quick Setup

### Current GoDaddy DNS → Cloudflare DNS

1. **Get Cloudflare Nameservers**
   - After adding linknode.com to Cloudflare, you'll see 2 nameservers
   - Example: `anna.ns.cloudflare.com` and `bob.ns.cloudflare.com`

2. **Update at GoDaddy**
   ```
   1. Log in to GoDaddy
   2. My Products → DNS → Manage Zones
   3. Find linknode.com
   4. Click "Change Nameservers"
   5. Choose "I'll use my own nameservers"
   6. Remove GoDaddy nameservers
   7. Add Cloudflare nameservers
   8. Save
   ```

3. **Wait for Propagation**
   - Usually 15-60 minutes
   - Maximum 24-48 hours
   - Check status: https://dnschecker.org/#NS/linknode.com

## 📋 Cloudflare DNS Records

Once nameservers are updated, add these in Cloudflare:

### Required Records

| Type | Name | Content | TTL | Proxy |
|------|------|---------|-----|-------|
| A | @ | 192.0.2.1 | Auto | ✅ Proxied |
| CNAME | www | linknode.com | Auto | ✅ Proxied |

### Why 192.0.2.1?
- This is a "dummy" IP from the documentation range
- Cloudflare Worker intercepts all traffic before it reaches this IP
- The actual backend (119.9.118.22:32304) is defined in the Worker

### Optional Records (if you use email)

| Type | Name | Content | TTL | Proxy |
|------|------|---------|-----|-------|
| MX | @ | mail.linknode.com | Auto | ❌ DNS only |
| TXT | @ | v=spf1 include:_spf.google.com ~all | Auto | ❌ DNS only |

## 🔄 Worker Route Configuration

1. Go to **Workers Routes** in Cloudflare
2. Add these routes:

| Route | Worker | Status |
|-------|--------|--------|
| linknode.com/* | linknode-proxy | Active |
| www.linknode.com/* | linknode-proxy | Active |

## ⚡ SSL/TLS Settings

1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **Flexible**
   - Frontend (User ↔ Cloudflare): HTTPS
   - Backend (Cloudflare ↔ Your Server): HTTP

3. Go to **SSL/TLS** → **Edge Certificates**
4. Enable:
   - ✅ Always Use HTTPS
   - ✅ Automatic HTTPS Rewrites
   - ✅ Opportunistic Encryption

## 🚀 Testing Your Setup

### 1. Check Nameservers
```bash
nslookup -type=NS linknode.com
```
Should show Cloudflare nameservers

### 2. Check DNS Records
```bash
nslookup linknode.com
```
Should show Cloudflare IPs (104.x.x.x or 172.x.x.x)

### 3. Check Worker
```bash
curl -I https://linknode.com
```
Should return headers from your app

### 4. Browser Test
- Visit https://linknode.com
- Should see your Kubernetes app
- Check for SSL padlock

## 🔧 Advanced Configuration

### Redirect www to non-www
Add a Page Rule:
- URL: `www.linknode.com/*`
- Setting: Forwarding URL (301)
- Destination: `https://linknode.com/$1`

### Force HTTPS
Add a Page Rule:
- URL: `http://*linknode.com/*`
- Setting: Always Use HTTPS

### Cache Static Assets
Add a Page Rule:
- URL: `*linknode.com/*.{jpg,jpeg,png,gif,css,js}`
- Setting: Cache Level - Cache Everything
- Setting: Edge Cache TTL - 1 month

## 📊 Monitoring

1. **Analytics**: Check visitor stats in Cloudflare dashboard
2. **Workers**: Monitor requests and errors
3. **DNS**: Use Cloudflare's DNS analytics

## 🚨 Common Issues

### "Website not found"
- DNS hasn't propagated yet
- Worker route not configured
- Wrong nameservers at GoDaddy

### SSL Certificate Error
- Wait 15 minutes for Cloudflare to issue certificate
- Check SSL/TLS mode is "Flexible"

### Seeing GoDaddy Parking Page
- Clear browser cache
- Try incognito mode
- DNS still pointing to GoDaddy

### 520/521/522 Errors
- Backend server (119.9.118.22:32304) is down
- Check your Kubernetes app is running