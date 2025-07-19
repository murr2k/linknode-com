# Cloudflare Setup Documentation

## Overview
This setup uses Cloudflare Workers to redirect linknode.com to your Kubernetes application at http://119.9.118.22:32304.

## Important Limitation
Cloudflare Workers **cannot directly proxy to IP addresses** due to security restrictions. This is why we use a redirect approach instead of a true reverse proxy.

## Current Implementation
The Worker serves a redirect page that:
1. Shows a professional loading screen matching your app's branding
2. Automatically redirects to http://119.9.118.22:32304
3. Provides a manual link if auto-redirect fails

## Files Created
- `worker.js` - The redirect worker script
- `setup-with-env.sh` - Automated setup script
- `upload-worker.sh` - Direct worker upload script
- `.env` - Contains your Cloudflare API credentials (gitignored)
- `alternative-solutions.md` - Other approaches for true proxying

## DNS Configuration
Your domain is configured with:
- A record: linknode.com → 192.0.2.1 (dummy IP, proxied through Cloudflare)
- CNAME record: www.linknode.com → linknode.com
- Worker route: *linknode.com/* → linknode-proxy worker

## How It Works
1. User visits https://linknode.com
2. Cloudflare routes the request to your Worker
3. Worker returns an HTML page with meta refresh and JavaScript redirect
4. User's browser redirects to http://119.9.118.22:32304

## Limitations
- URL bar will show the IP address after redirect
- HTTPS is only available on linknode.com, not on the final destination
- Cannot mask the backend URL

## Alternative Solutions
If you need true reverse proxying (URL masking), consider:
1. **Cloudflare Tunnel**: Install cloudflared on a server that can reach your cluster
2. **VPS Proxy**: Deploy nginx on a VPS with a domain name
3. **Platform Hosting**: Use Heroku, Railway, or similar with custom domains
4. **Ngrok**: Create a tunnel with a custom domain

## Testing
Visit https://linknode.com to see the redirect in action.

## Maintenance
To update the redirect target:
1. Edit the `backendUrl` in worker.js
2. Run `./upload-worker.sh` to deploy changes