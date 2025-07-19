addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // Service URLs
  const tunnelUrl = 'https://daniel-holidays-diesel-gross.trycloudflare.com'
  const nginxDirectUrl = 'http://119.9.118.22:30898'
  const monitoringDirectUrl = 'http://119.9.118.22:30500'
  const grafanaDirectUrl = 'http://119.9.118.22:30300'
  
  // Route to monitoring service for API endpoints
  if (url.pathname.startsWith('/api/power-data')) {
    // Clone the request to modify it
    const modifiedRequest = new Request(monitoringDirectUrl + url.pathname + url.search, {
      method: request.method,
      headers: request.headers,
      body: request.body
    })
    
    // Forward the request to the monitoring service
    const response = await fetch(modifiedRequest)
    
    // Return the response with CORS headers for browser access
    const modifiedResponse = new Response(response.body, response)
    modifiedResponse.headers.set('Access-Control-Allow-Origin', '*')
    modifiedResponse.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    modifiedResponse.headers.set('Access-Control-Allow-Headers', 'Content-Type')
    
    return modifiedResponse
  }
  
  // Route to Grafana dashboard
  if (url.pathname.startsWith('/grafana')) {
    return Response.redirect(grafanaDirectUrl + url.pathname.replace('/grafana', '') + url.search, 302)
  }
  
  // For the root path, return an enhanced landing page
  if (url.pathname === '/' || url.pathname === '') {
    return new Response(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rackspace K8s Demo - Linknode</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #0f0f0f;
            color: #fff;
            padding: 20px;
        }
        .container {
            text-align: center;
            max-width: 800px;
            width: 100%;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            color: #999;
            margin-bottom: 3rem;
            font-size: 1.1rem;
        }
        .options {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-top: 2rem;
        }
        .option {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 2rem;
            border: 1px solid #333;
            transition: all 0.3s;
        }
        .option:hover {
            border-color: #667eea;
            transform: translateY(-2px);
        }
        .option h2 {
            margin: 0 0 0.5rem 0;
            color: #667eea;
            font-size: 1.3rem;
        }
        .option p {
            margin: 0 0 1rem 0;
            color: #ccc;
            font-size: 0.95rem;
        }
        a.button {
            display: inline-block;
            padding: 0.75rem 2rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            transition: all 0.2s;
            font-weight: 500;
        }
        a.button:hover {
            background: #764ba2;
            transform: translateY(-1px);
        }
        .secondary {
            background: transparent;
            border: 2px solid #667eea;
            color: #667eea;
        }
        .secondary:hover {
            background: #667eea;
            color: white;
        }
        .monitoring {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .monitoring:hover {
            opacity: 0.9;
        }
        .grafana {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        .grafana:hover {
            opacity: 0.9;
        }
        .note {
            margin-top: 3rem;
            padding: 1rem;
            background: #1a1a1a;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #999;
        }
        .new-badge {
            display: inline-block;
            background: #f5576c;
            color: white;
            font-size: 0.7rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            margin-left: 0.5rem;
            vertical-align: super;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Rackspace K8s Demo</h1>
        <p class="subtitle">Choose your destination</p>
        
        <div class="options">
            <div class="option">
                <h2>🚀 Via Cloudflare Tunnel</h2>
                <p>Access through Cloudflare's secure tunnel with HTTPS</p>
                <a href="${tunnelUrl}" class="button" target="_blank">Open Secure Version</a>
            </div>
            
            <div class="option">
                <h2>🔗 Direct Access</h2>
                <p>Connect directly to the Kubernetes cluster</p>
                <a href="${nginxDirectUrl}" class="button secondary" target="_blank">Open Direct Version</a>
            </div>
            
            <div class="option">
                <h2>⚡ Power Monitoring<span class="new-badge">NEW</span></h2>
                <p>Monitor real-time power consumption data</p>
                <a href="${monitoringDirectUrl}" class="button monitoring" target="_blank">Open Dashboard</a>
            </div>
            
            <div class="option">
                <h2>📊 Grafana Analytics<span class="new-badge">NEW</span></h2>
                <p>Visualize power metrics and trends</p>
                <a href="${grafanaDirectUrl}" class="button grafana" target="_blank">Open Grafana</a>
            </div>
        </div>
        
        <div class="note">
            <strong>Power Monitoring API:</strong> Configure your EAGLE device to send data to 
            <code>https://linknode.com/api/power-data</code> using JSON format.
        </div>
    </div>
</body>
</html>
    `, {
      status: 200,
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate'
      }
    })
  }
  
  // For other paths, redirect to the tunnel URL
  const targetUrl = tunnelUrl + url.pathname + url.search
  return Response.redirect(targetUrl, 302)
}