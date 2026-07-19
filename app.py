from flask import Flask, jsonify
import os
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return "<h1>SaaS Web Application is running smoothly!</h1>"

@app.route('/healthz')
def healthz():
    # Essential for Kubernetes liveness/readiness probes
    return jsonify({"status": "healthy"}), 200

@app.route('/load')
def load():
    # Generates intentional CPU load to trigger the autoscaler
    start_time = time.time()
    while time.time() - start_time < 0.3:
        _ = 25000 * 25000
    return "<h1>CPU load generated successfully!</h1>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
