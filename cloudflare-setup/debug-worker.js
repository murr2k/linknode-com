addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // If path is /debug, show debug info
  if (url.pathname === '/debug') {
    return new Response(JSON.stringify({
      request_url: request.url,
      backend_url: 'http://119.9.118.22:32304',
      cf_ray: request.headers.get('cf-ray'),
      timestamp: new Date().toISOString()
    }, null, 2), {
      headers: { 'content-type': 'application/json' }
    })
  }
  
  // Try to fetch from backend
  const backendUrl = 'http://119.9.118.22:32304'
  const targetUrl = backendUrl + url.pathname + url.search
  
  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      redirect: 'manual'
    })
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers
    })
  } catch (error) {
    // Return error details
    return new Response(JSON.stringify({
      error: error.message,
      backend: backendUrl,
      target: targetUrl,
      stack: error.stack
    }, null, 2), {
      status: 503,
      headers: { 'content-type': 'application/json' }
    })
  }
}