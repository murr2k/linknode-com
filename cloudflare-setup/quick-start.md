# 🚀 Cloudflare Quick Start Guide

Get linknode.com working in 15 minutes!

## Step 1: Sign Up for Cloudflare (2 min)
1. Go to https://cloudflare.com
2. Click "Sign Up"
3. Enter email and password
4. Verify your email

## Step 2: Add Your Site (3 min)
1. Click "Add a Site"
2. Type: `linknode.com`
3. Click "Add Site"
4. Select **FREE plan**
5. Click "Continue"

## Step 3: Copy Nameservers (1 min)
Cloudflare will show 2 nameservers. Copy them:
- Example: `anna.ns.cloudflare.com`
- Example: `bob.ns.cloudflare.com`

## Step 4: Update GoDaddy (5 min)
1. Open new tab: https://dcc.godaddy.com
2. Sign in to GoDaddy
3. Click "My Domains"
4. Find `linknode.com` → Click "Manage"
5. Scroll to "Nameservers" → Click "Change"
6. Choose "Enter my own nameservers"
7. Delete existing ones
8. Add Cloudflare's nameservers
9. Save

## Step 5: Create Worker (3 min)
Back in Cloudflare:
1. Click "Workers & Pages" (left sidebar)
2. Click "Create Application"
3. Click "Create Worker"
4. Name: `linknode-proxy`
5. Click "Deploy"
6. Click "Edit Code"
7. Delete all existing code
8. Copy ALL content from `worker.js` file
9. Paste it
10. Click "Save and Deploy"

## Step 6: Configure DNS (2 min)
1. Go back to main dashboard
2. Click on `linknode.com`
3. Click "DNS" (left sidebar)
4. Delete any existing records
5. Add new record:
   - Type: `A`
   - Name: `@`
   - IPv4: `192.0.2.1`
   - Proxy: ✅ ON (orange cloud)
   - Click "Save"
6. Add another:
   - Type: `CNAME`
   - Name: `www`
   - Target: `linknode.com`
   - Proxy: ✅ ON (orange cloud)
   - Click "Save"

## Step 7: Create Route (2 min)
1. Still in your domain, click "Workers Routes"
2. Click "Add route"
3. Route: `*linknode.com/*`
4. Worker: Select `linknode-proxy`
5. Click "Save"

## Step 8: Configure SSL (1 min)
1. Click "SSL/TLS" (left sidebar)
2. Select "Flexible"
3. Click "Edge Certificates" 
4. Turn ON "Always Use HTTPS"

## ✅ Done! Now Wait...
- DNS changes take 5-60 minutes usually
- Check progress: https://dnschecker.org/#NS/linknode.com
- When it shows Cloudflare nameservers, you're ready!
- Visit https://linknode.com

## 🎯 Quick Test
```bash
# Check if DNS has propagated
nslookup linknode.com

# Should show Cloudflare IPs like:
# 104.x.x.x or 172.x.x.x
```

## ❓ Not Working?
1. Clear browser cache (Ctrl+Shift+R)
2. Try incognito/private mode
3. Wait up to 24 hours for full propagation
4. Check worker logs in Cloudflare dashboard

## 🎉 Success Checklist
- [ ] Cloudflare nameservers set at GoDaddy
- [ ] Worker deployed and active
- [ ] DNS records added (A and CNAME)
- [ ] Worker route configured
- [ ] SSL set to Flexible
- [ ] Site loads at https://linknode.com

That's it! Your domain now proxies to your Kubernetes app with no visible port number!