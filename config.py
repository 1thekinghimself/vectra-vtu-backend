"""
Configuration module for Vectra VTU Backend
Updated for better debugging
"""
import os
import sys

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'Vectra_secret_key_2026_1.0')
    
    # Use absolute path for SQLite database
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "vectra.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # IA Café API Configuration
    IACAFE_API_KEY = os.getenv('IACAFE_API_KEY', 'ak_live_e1da24fac34d645d6fc63a8585996dbb2acd72bb7b16c509')
    IACAFE_BASE_URL = 'https://iacafe.com.ng/devapi/v1'
    IACAFE_WEBHOOK_SECRET = os.getenv('IACAFE_WEBHOOK_SECRET', 'vectra_iacafe_webhook_secret_2026_IWSF1')
    
    # Application Settings
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Debug info
    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ON_PYTHONANYWHERE = 'pythonanywhere' in os.environ.get('HOME', '')
    
    @classmethod
    def print_debug_info(cls):
        """Print debug information"""
        print("\n🔧 Configuration Debug Info:")
        print(f"   Python Version: {cls.PYTHON_VERSION}")
        print(f"   On PythonAnywhere: {cls.ON_PYTHONANYWHERE}")
        print(f"   Debug Mode: {cls.DEBUG}")
        print(f"   Database URI: {cls.SQLALCHEMY_DATABASE_URI}")
        print(f"   IA Café Base URL: {cls.IACAFE_BASE_URL}")
        print(f"   IA Café API Key present: {'Yes' if cls.IACAFE_API_KEY else 'No'}")
        if cls.IACAFE_API_KEY:
            print(f"   IA Café API Key (first/last 4): {cls.IACAFE_API_KEY[:4]}...{cls.IACAFE_API_KEY[-4:]}")
        print(f"   Webhook Secret present: {'Yes' if cls.IACAFE_WEBHOOK_SECRET else 'No'}")
    
    # Validate critical environment variables
    @classmethod
    def validate_config(cls):
        """Validate that all required environment variables are set"""
        cls.print_debug_info()
        
        print(f"\n🔍 Validating configuration...")
        
        missing = []
        if not cls.IACAFE_API_KEY:
            missing.append('IACAFE_API_KEY')
        if not cls.IACAFE_WEBHOOK_SECRET:
            missing.append('IACAFE_WEBHOOK_SECRET')
        
        if missing:
            error_msg = f"Missing required environment variables: {', '.join(missing)}"
            print(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        print(f"✅ Configuration validated successfully")
        return True

# Create configuration instance
config = Config()