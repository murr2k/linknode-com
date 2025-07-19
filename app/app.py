from flask import Flask, jsonify, render_template_string
import os
import socket
import datetime
import requests
from power_monitor import power_monitor

app = Flask(__name__)

# Register the power monitoring blueprint
app.register_blueprint(power_monitor)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Kubernetes Demo - Cloud Info Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .info-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .info-item {
            margin: 10px 0;
            padding: 10px;
            background-color: #f8f8f8;
            border-radius: 4px;
        }
        .label {
            font-weight: bold;
            color: #555;
        }
        .value {
            color: #333;
        }
        .status {
            text-align: center;
            font-size: 24px;
            margin: 20px 0;
        }
        .healthy {
            color: #4CAF50;
        }
        .error {
            color: #f44336;
        }
    </style>
    <meta http-equiv="refresh" content="5">
</head>
<body>
    <div class="container">
        <h1>🚀 Kubernetes Demo Application</h1>
        <div class="status {{ health_class }}">{{ health_status }}</div>
        
        <div class="info-card">
            <h2>📦 Pod Information</h2>
            <div class="info-item">
                <span class="label">Pod Name:</span>
                <span class="value">{{ pod_name }}</span>
            </div>
            <div class="info-item">
                <span class="label">Node Name:</span>
                <span class="value">{{ node_name }}</span>
            </div>
            <div class="info-item">
                <span class="label">Namespace:</span>
                <span class="value">{{ namespace }}</span>
            </div>
            <div class="info-item">
                <span class="label">Service Account:</span>
                <span class="value">{{ service_account }}</span>
            </div>
        </div>
        
        <div class="info-card">
            <h2>🖥️ System Information</h2>
            <div class="info-item">
                <span class="label">Hostname:</span>
                <span class="value">{{ hostname }}</span>
            </div>
            <div class="info-item">
                <span class="label">IP Address:</span>
                <span class="value">{{ ip_address }}</span>
            </div>
            <div class="info-item">
                <span class="label">Current Time:</span>
                <span class="value">{{ current_time }}</span>
            </div>
            <div class="info-item">
                <span class="label">App Version:</span>
                <span class="value">{{ app_version }}</span>
            </div>
        </div>
        
        <div class="info-card">
            <h2>⚙️ Configuration</h2>
            <div class="info-item">
                <span class="label">Environment:</span>
                <span class="value">{{ environment }}</span>
            </div>
            <div class="info-item">
                <span class="label">Feature Flag:</span>
                <span class="value">{{ feature_flag }}</span>
            </div>
            <div class="info-item">
                <span class="label">Database URL:</span>
                <span class="value">{{ db_url }}</span>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    try:
        # Get pod information from environment variables
        pod_name = os.environ.get('HOSTNAME', 'Unknown')
        node_name = os.environ.get('NODE_NAME', 'Unknown')
        namespace = os.environ.get('POD_NAMESPACE', 'Unknown')
        service_account = os.environ.get('SERVICE_ACCOUNT', 'Unknown')
        
        # Get system information
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Get configuration from environment
        app_version = os.environ.get('APP_VERSION', '1.0.0')
        environment = os.environ.get('ENVIRONMENT', 'development')
        feature_flag = os.environ.get('FEATURE_FLAG', 'disabled')
        db_url = os.environ.get('DATABASE_URL', 'Not configured')
        
        return render_template_string(HTML_TEMPLATE,
            health_status='✅ Healthy',
            health_class='healthy',
            pod_name=pod_name,
            node_name=node_name,
            namespace=namespace,
            service_account=service_account,
            hostname=hostname,
            ip_address=ip_address,
            current_time=current_time,
            app_version=app_version,
            environment=environment,
            feature_flag=feature_flag,
            db_url=db_url
        )
    except Exception as e:
        return render_template_string(HTML_TEMPLATE,
            health_status='❌ Error',
            health_class='error',
            pod_name='Error',
            node_name='Error',
            namespace='Error',
            service_account='Error',
            hostname='Error',
            ip_address='Error',
            current_time='Error',
            app_version='Error',
            environment='Error',
            feature_flag='Error',
            db_url='Error'
        )

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

@app.route('/ready')
def ready():
    # Simple readiness check - in real app, might check database connection, etc.
    return jsonify({'status': 'ready', 'timestamp': datetime.datetime.now().isoformat()})

@app.route('/api/info')
def api_info():
    return jsonify({
        'pod': {
            'name': os.environ.get('HOSTNAME', 'Unknown'),
            'namespace': os.environ.get('POD_NAMESPACE', 'Unknown'),
            'node': os.environ.get('NODE_NAME', 'Unknown')
        },
        'app': {
            'version': os.environ.get('APP_VERSION', '1.0.0'),
            'environment': os.environ.get('ENVIRONMENT', 'development')
        },
        'system': {
            'hostname': socket.gethostname(),
            'ip': socket.gethostbyname(socket.gethostname()),
            'time': datetime.datetime.now().isoformat()
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)