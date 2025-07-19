addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // Enhanced debug endpoint
  if (url.pathname === '/debug') {
    const backendUrl = 'http://119.9.118.22:32304'
    let backendTest = { status: 'not_tested', error: null }
    
    // Try to fetch from backend
    try {
      const testResponse = await fetch(backendUrl, {
        method: 'GET',
        headers: {
          'User-Agent': 'Cloudflare-Worker-Test'
        }
      })
      backendTest = {
        status: 'success',
        http_status: testResponse.status,
        statusText: testResponse.statusText,
        headers: Object.fromEntries(testResponse.headers.entries())
      }
    } catch (error) {
      backendTest = {
        status: 'failed',
        error: error.message,
        error_type: error.constructor.name
      }
    }
    
    return new Response(JSON.stringify({
      request_info: {
        url: request.url,
        method: request.method,
        headers: Object.fromEntries(request.headers.entries()),
        cf: request.cf
      },
      backend_info: {
        url: backendUrl,
        test_result: backendTest
      },
      worker_info: {
        timestamp: new Date().toISOString(),
        cf_ray: request.headers.get('cf-ray')
      }
    }, null, 2), {
      headers: { 'content-type': 'application/json' }
    })
  }
  
  // Main proxy logic with better error handling
  const backendUrl = 'http://119.9.118.22:32304'
  const targetUrl = backendUrl + url.pathname + url.search
  
  try {
    // Log for debugging
    console.log('Proxying request to:', targetUrl)
    
    // Create a new request with modified headers
    const modifiedHeaders = new Headers(request.headers)
    
    // Remove Cloudflare-specific headers
    const cfHeaders = ['cf-ray', 'cf-visitor', 'cf-request-id', 'cf-connecting-ip', 'cf-ipcountry']
    cfHeaders.forEach(header => modifiedHeaders.delete(header))
    
    // Set a custom User-Agent
    modifiedHeaders.set('User-Agent', 'Cloudflare-Worker-Proxy')
    
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: modifiedHeaders,
      redirect: 'follow'  // Changed from 'manual' to 'follow'
    })
    
    // Clone the response to modify headers
    const responseHeaders = new Headers(response.headers)
    responseHeaders.set('X-Proxied-By', 'Cloudflare-Worker')
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders
    })
    
  } catch (error) {
    console.error('Proxy error:', error)
    
    // Return detailed error information
    return new Response(JSON.stringify({
      error: 'Failed to proxy request',
      message: error.message,
      backend: backendUrl,
      target: targetUrl,
      error_type: error.constructor.name,
      timestamp: new Date().toISOString()
    }, null, 2), {
      status: 502,
      headers: { 
        'content-type': 'application/json',
        'X-Error-Type': 'proxy-failure'
      }
    })
  }
}