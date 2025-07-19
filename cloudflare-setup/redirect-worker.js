addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const backendUrl = 'http://119.9.118.22:32304'
  
  // For the root path, return HTML with meta refresh
  if (url.pathname === '/' || url.pathname === '') {
    return new Response(`
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="0; url=${backendUrl}">
    <title>Redirecting to Rackspace K8s Demo...</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #0f0f0f;
            color: #fff;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 2rem;
            margin-bottom: 1rem;
        }
        p {
            color: #999;
            margin-bottom: 2rem;
        }
        a {
            color: #667eea;
            text-decoration: none;
            padding: 0.75rem 1.5rem;
            border: 2px solid #667eea;
            border-radius: 0.25rem;
            display: inline-block;
            transition: all 0.2s;
        }
        a:hover {
            background: #667eea;
            color: white;
        }
        .spinner {
            margin: 2rem auto;
            width: 50px;
            height: 50px;
            border: 3px solid #333;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Redirecting to Rackspace K8s Demo</h1>
        <div class="spinner"></div>
        <p>You are being redirected to the demo application...</p>
        <p>If you are not redirected automatically, <a href="${backendUrl}">click here</a>.</p>
    </div>
    <script>
        // Fallback JavaScript redirect
        setTimeout(function() {
            window.location.href = '${backendUrl}';
        }, 100);
    </script>
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
  
  // For other paths, return a 302 redirect
  const targetUrl = backendUrl + url.pathname + url.search
  return Response.redirect(targetUrl, 302)
}