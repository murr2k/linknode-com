# Cloudflare Setup for linknode.com

This guide will help you set up Cloudflare to proxy linknode.com to your Kubernetes application at http://119.9.118.22:32304.

## 🚀 Quick Overview

Cloudflare will:
- Hide the port number (visitors see linknode.com, not :32304)
- Provide free SSL/HTTPS
- Cache static content
- Protect against DDoS
- Give you analytics

## 📋 Step-by-Step Setup

### Step 1: Create Cloudflare Account

1. Go to https://dash.cloudflare.com/sign-up
2. Create a free account
3. Verify your email

### Step 2: Add Your Domain

1. Click "Add a Site" in Cloudflare dashboard
2. Enter `linknode.com`
3. Select the **FREE** plan
4. Cloudflare will scan your existing DNS records

### Step 3: Update Nameservers at GoDaddy

1. Cloudflare will show you 2 nameservers like:
   - `xxx.ns.cloudflare.com`
   - `yyy.ns.cloudflare.com`

2. Log into GoDaddy:
   - Go to: https://dcc.godaddy.com/domains/
   - Click on `linknode.com`
   - Click "Manage DNS" or "Nameservers"
   - Choose "Change Nameservers"
   - Select "Enter my own nameservers (advanced)"
   - Enter the Cloudflare nameservers
   - Save changes

3. Wait for propagation (5 minutes to 24 hours, usually ~30 minutes)

### Step 4: Configure Cloudflare Worker

1. In Cloudflare dashboard, go to **Workers & Pages**
2. Click "Create Application" → "Create Worker"
3. Name it: `linknode-proxy`
4. Click "Deploy"
5. Click "Edit Code"
6. Replace with the worker script from `worker.js`
7. Click "Save and Deploy"

### Step 5: Set Up Route

1. Go back to your domain in Cloudflare
2. Go to **Workers Routes**
3. Click "Add route"
4. Route: `linknode.com/*`
5. Worker: Select `linknode-proxy`
6. Save

### Step 6: Configure DNS

1. In Cloudflare, go to **DNS** for linknode.com
2. Delete any existing A records for @ or www
3. Add these records:

| Type | Name | Content | Proxy Status |
|------|------|---------|--------------|
| A | @ | 192.0.2.1 | Proxied (Orange) |
| CNAME | www | linknode.com | Proxied (Orange) |

**Note**: The IP 192.0.2.1 is a dummy IP - the Worker will intercept all traffic.

## 🔧 Alternative: Using Page Rules (Simpler but Limited)

If Workers seem complex, try Page Rules:

1. Go to **Page Rules** in Cloudflare
2. Create a page rule:
   - URL: `linknode.com/*`
   - Setting: "Forwarding URL" (301)
   - Destination: `http://119.9.118.22:32304/$1`
3. Save

**Limitation**: This redirects (shows the port in the URL) rather than proxying.

## ✅ Testing

1. Use DNS checker: https://dnschecker.org/#A/linknode.com
2. Once DNS propagates, visit https://linknode.com
3. You should see your Kubernetes app!

## 🔒 Enable HTTPS

1. In Cloudflare, go to **SSL/TLS**
2. Set mode to "Flexible" (since your backend is HTTP)
3. Enable "Always Use HTTPS"

## 📊 Features You Get Free

- ✅ Hide port number
- ✅ Free SSL certificate
- ✅ DDoS protection
- ✅ Analytics
- ✅ Caching
- ✅ Page rules (3 free)
- ✅ Workers (100,000 requests/day free)

## 🚨 Troubleshooting

### DNS Not Propagating
- Check at: https://dnschecker.org
- Wait up to 24 hours
- Verify nameservers at GoDaddy

### Worker Not Running
- Check Workers dashboard for errors
- Verify route is active
- Check worker logs

### SSL Errors
- Set SSL mode to "Flexible"
- Wait 15 minutes for certificate

### Still Seeing GoDaddy Page
- Clear browser cache
- Try incognito mode
- DNS might still be propagating

## 📞 Support

- Cloudflare Community: https://community.cloudflare.com
- Status Page: https://www.cloudflarestatus.com