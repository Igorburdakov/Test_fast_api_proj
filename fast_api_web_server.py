from flask import Flask, request, jsonify
import requests
import threading
import os
import time
import logging
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger( __name__ )

app = Flask( __name__ )
BACKEND_API_URL = os.getenv("BACKEND_URL", "http://backend:5001/api/process")
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 60))
MAX_REQUESTS_PER_IP = int(os.getenv("MAX_REQUESTS_PER_IP", 20))

ip_requests = defaultdict( list )
ip_lock = threading.Lock()

executor = ThreadPoolExecutor( max_workers=MAX_CONCURRENT_REQUESTS )


def check_rate_limit(ip):
    with ip_lock:
        now = time.time()
        ip_requests[ip] = [req_time for req_time in ip_requests[ip]
                           if now - req_time < RATE_LIMIT_WINDOW]

        if len( ip_requests[ip] ) >= MAX_REQUESTS_PER_IP:
            return False

        ip_requests[ip].append( now )
        return True


def process_backend_request(number, ip):
    try:
        logger.info( f"Processing request for IP {ip}, number {number}" )

        response = requests.post(
            BACKEND_API_URL,
            json={"number": number},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        return response.json(), response.status_code

    except requests.exceptions.Timeout:
        logger.error( f"Backend timeout for IP {ip}" )
        return {"error": "Backend timeout"}, 504
    except requests.exceptions.ConnectionError:
        logger.error( f"Cannot connect to backend from IP {ip}" )
        return {"error": "Cannot connect to backend"}, 502
    except Exception as e:
        logger.error( f"Unexpected error for IP {ip}: {e}" )
        return {"error": "Internal server error"}, 500


@app.route( '/api/process', methods=['POST'] )
def process_number():
    if not request.is_json:
        return jsonify( {"error": "Content-Type must be application/json"} ), 415

    data = request.get_json()

    if not data or 'number' not in data:
        return jsonify( {"error": "Field 'number' is required"} ), 400

    number = data['number']

    if not isinstance( number, (int, float) ):
        return jsonify( {"error": "Number must be numeric"} ), 400

    if number < 0 or number != int( number ):
        return jsonify( {"error": "Number must be non-negative integer"} ), 400

    number = int( number )
    ip = request.remote_addr

    if not check_rate_limit( ip ):
        return jsonify( {
            "error": f"Rate limit exceeded. Max {MAX_REQUESTS_PER_IP} requests per {RATE_LIMIT_WINDOW}s"
        } ), 429

    try:
        future = executor.submit( process_backend_request, number, ip )
        result, status_code = future.result( timeout=15 )  # Таймаут 15 секунд

        return jsonify( result ), status_code

    except Exception as e:
        logger.error( f"Error processing request from IP {ip}: {e}" )
        return jsonify( {"error": "Request processing failed"} ), 500


@app.route( '/health', methods=['GET'] )
def health_check():
    try:
        backend_response = requests.get( "http://backend:5001/health", timeout=3 )
        backend_ok = backend_response.status_code == 200

        thread_pool_stats = {
            "active_threads": executor._work_queue.qsize(),
            "max_workers": executor._max_workers,
            "pending_tasks": len( [f for f in executor._futures if not f.done()] )
        }

        return jsonify( {
            "frontend": "healthy",
            "backend": "healthy" if backend_ok else "unhealthy",
            "thread_pool": thread_pool_stats,
            "rate_limiting": {
                "window_seconds": RATE_LIMIT_WINDOW,
                "max_per_ip": MAX_REQUESTS_PER_IP
            }
        } ), 200 if backend_ok else 503

    except Exception as e:
        return jsonify( {
            "frontend": "healthy",
            "backend": "unreachable",
            "error": str( e )
        } ), 503


@app.route( '/api/queue/stats', methods=['GET'] )
def get_queue_stats():
    with ip_lock:
        ip_stats = {}
        now = time.time()

        for ip, requests_list in ip_requests.items():
            recent_requests = [req_time for req_time in requests_list
                               if now - req_time < RATE_LIMIT_WINDOW]
            ip_stats[ip] = {
                "requests_in_window": len( recent_requests ),
                "remaining_quota": max( 0, MAX_REQUESTS_PER_IP - len( recent_requests ) )
            }

        return jsonify( {
            "total_unique_ips": len( ip_stats ),
            "rate_limit_window_seconds": RATE_LIMIT_WINDOW,
            "max_requests_per_ip": MAX_REQUESTS_PER_IP,
            "ip_statistics": ip_stats
        } )


def cleanup():
    executor.shutdown( wait=True )
    logger.info( "Thread pool shutdown complete" )


if __name__ == "__main__":
    try:
        logger.info( f"Starting Flask server with {MAX_CONCURRENT_REQUESTS} concurrent workers" )
        app.run(
            host="0.0.0.0",
            port=int(os.getenv("FRONTEND_PORT", 5000)),
            debug=False,
            threaded=True
        )
    finally:
        cleanup()