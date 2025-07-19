addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // The quick tunnel URL (update this when you run a new tunnel)
  const tunnelUrl = 'https://daniel-holidays-diesel-gross.trycloudflare.com'
  const directUrl = 'http://119.9.118.22:30898'
  
  // For the root path, return a nice page with both options
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
            max-width: 600px;
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
            display: flex;
            flex-direction: column;
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
        }
        .option p {
            margin: 0 0 1rem 0;
            color: #ccc;
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
        .note {
            margin-top: 3rem;
            padding: 1rem;
            background: #1a1a1a;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #999;
        }
        @media (min-width: 768px) {
            .options {
                flex-direction: row;
            }
            .option {
                flex: 1;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Rackspace K8s Demo</h1>
        <p class="subtitle">Choose how you'd like to access the application</p>
        
        <div class="options">
            <div class="option">
                <h2>🚀 Via Cloudflare Tunnel</h2>
                <p>Access through Cloudflare's secure tunnel with HTTPS</p>
                <a href="${tunnelUrl}" class="button" target="_blank">Open Secure Version</a>
            </div>
            
            <div class="option">
                <h2>🔗 Direct Access</h2>
                <p>Connect directly to the Kubernetes cluster</p>
                <a href="${directUrl}" class="button secondary" target="_blank">Open Direct Version</a>
            </div>
        </div>
        
        <div class="note">
            <strong>Note:</strong> The tunnel URL provides secure HTTPS access through Cloudflare's network, 
            while direct access connects straight to the Kubernetes NodePort service.
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