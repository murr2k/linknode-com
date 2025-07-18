/**
 * Cloudflare Worker Script for linknode.com
 * Proxies requests to Kubernetes app at http://119.9.118.22:32304
 */

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // Target backend URL
  const backendUrl = 'http://119.9.118.22:32304'
  
  // Get the request URL
  const url = new URL(request.url)
  
  // Build the new URL with the backend host but keep the original path
  const targetUrl = backendUrl + url.pathname + url.search
  
  // Create modified request headers
  const modifiedHeaders = new Headers(request.headers)
  
  // Add/modify headers for the backend
  modifiedHeaders.set('X-Forwarded-Host', url.hostname)
  modifiedHeaders.set('X-Forwarded-Proto', url.protocol.replace(':', ''))
  modifiedHeaders.set('X-Real-IP', request.headers.get('CF-Connecting-IP') || '')
  
  // Remove Cloudflare headers that might confuse the backend
  modifiedHeaders.delete('cf-ray')
  modifiedHeaders.delete('cf-visitor')
  modifiedHeaders.delete('cf-request-id')
  
  // Create the fetch options
  const init = {
    method: request.method,
    headers: modifiedHeaders,
    redirect: 'manual'
  }
  
  // Include body for POST, PUT, etc.
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    init.body = request.body
  }
  
  try {
    // Fetch from backend
    const response = await fetch(targetUrl, init)
    
    // Handle redirects
    if (response.status >= 301 && response.status <= 308) {
      const location = response.headers.get('location')
      if (location) {
        // If the redirect is to the backend URL, replace it with our domain
        const newLocation = location.replace(backendUrl, 'https://linknode.com')
        const newHeaders = new Headers(response.headers)
        newHeaders.set('location', newLocation)
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: newHeaders
        })
      }
    }
    
    // Create modified response headers
    const responseHeaders = new Headers(response.headers)
    
    // Add CORS headers if needed
    responseHeaders.set('Access-Control-Allow-Origin', '*')
    
    // Add security headers
    responseHeaders.set('X-Content-Type-Options', 'nosniff')
    responseHeaders.set('X-Frame-Options', 'SAMEORIGIN')
    
    // Remove backend server info
    responseHeaders.delete('server')
    
    // Return the response
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders
    })
    
  } catch (error) {
    // Return error page if backend is down
    return new Response(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Error - linknode.com</title>
        <style>
          body { 
            font-family: sans-serif; 
            text-align: center; 
            padding: 50px;
            background: #f0f0f0;
          }
          h1 { color: #d32f2f; }
          p { color: #666; }
          .details { 
            background: white; 
            padding: 20px; 
            border-radius: 8px; 
            margin: 20px auto;
            max-width: 500px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          }
        </style>
      </head>
      <body>
        <h1>Service Temporarily Unavailable</h1>
        <div class="details">
          <p>We're having trouble connecting to the application server.</p>
          <p>Please try again in a few moments.</p>
          <p style="font-size: 12px; color: #999;">Error: ${error.message}</p>
        </div>
      </body>
      </html>
    `, {
      status: 503,
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'no-cache'
      }
    })
  }
}