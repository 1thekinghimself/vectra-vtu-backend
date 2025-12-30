"""
Main Flask application for Vectra VTU Backend
Initializes Flask app, registers blueprints, and sets up middleware
"""
from flask import Flask, jsonify, request
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from datetime import datetime

from config import config
from database import init_db
from routes.airtime import airtime_bp
from routes.data import data_bp
from routes.webhooks import webhooks_bp

def create_app():
    """Create and configure the Flask application"""
    
    # Initialize Flask app
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config)
    
    # Validate configuration
    try:
        config.validate_config()
        app.logger.info("✓ Configuration validated successfully")
    except ValueError as e:
        app.logger.error(f"✗ Configuration error: {e}")
        raise
    
    # CORS - Simple implementation without flask-cors
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # Initialize database
    with app.app_context():
        try:
            init_db()
            app.logger.info("✓ Database initialized")
        except Exception as e:
            app.logger.error(f"✗ Database initialization failed: {e}")
            raise
    
    # Register blueprints
    app.register_blueprint(airtime_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(webhooks_bp)
    app.logger.info("✓ Blueprints registered")
    
    # Configure logging
    if not app.debug:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'vectra.log'),
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Vectra VTU Backend startup')
    else:
        # Simple console logging for debug mode
        app.logger.setLevel(logging.DEBUG)
    
    # Request logging middleware
    @app.before_request
    def log_request_info():
        if request.path.startswith('/api/'):
            app.logger.info(f"API Request: {request.method} {request.path}")
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'message': 'Resource not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {str(error)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint for monitoring"""
        return jsonify({
            'status': 'healthy',
            'service': 'Vectra VTU Backend',
            'timestamp': datetime.now().isoformat(),
            'python_version': sys.version,
            'flask_version': '3.0.0'
        }), 200
    
    # Root endpoint
    @app.route('/', methods=['GET'])
    def index():
        """Root endpoint with API information"""
        return jsonify({
            'service': 'Vectra VTU Backend',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'airtime': '/api/v1/airtime',
                'data': '/api/v1/data',
                'webhooks': '/webhooks/iacafe',
                'health': '/health'
            },
            'documentation': 'https://vectraconnect.pythonanywhere.com/health'
        }), 200
    
    app.logger.info("✓ Flask application created successfully")
    return app

# Create application instance
app = create_app()

if __name__ == '__main__':
    # Run in development mode
    # In production, this will be served by PythonAnywhere's WSGI server
    print("Starting Vectra VTU Backend in development mode...")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=config.DEBUG
    )