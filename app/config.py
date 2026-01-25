"""
Configuration for Simonini-isms application
Uses the same database as Ruff Estimates (takeoff_pricing_db)
"""
import os
from dataclasses import dataclass

@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    def to_dict(self):
        return {
            'host': self.host,
            'port': self.port,
            'dbname': self.database,
            'user': self.user,
            'password': self.password
        }

# Database configuration - same as Ruff Estimates
DB_CONFIG = DatabaseConfig(
    host=os.getenv('DB_HOST', '31.97.137.221'),
    port=int(os.getenv('DB_PORT', '5432')),
    database=os.getenv('DB_NAME', 'takeoff_pricing_db'),
    user=os.getenv('DB_USER', 'Jon'),
    password=os.getenv('DB_PASSWORD', 'Transplant4real')
).to_dict()

# Flask configuration
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # Session configuration
    SESSION_COOKIE_NAME = 'session_token'
    SESSION_COOKIE_DOMAIN = os.getenv('COOKIE_DOMAIN', '.ruff.uno')
    SESSION_COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Ruff Estimates login URL for redirects
    RUFF_LOGIN_URL = os.getenv('RUFF_LOGIN_URL', 'https://ash.ruff.uno/login')

    # App URL for redirects
    APP_URL = os.getenv('APP_URL', 'https://isms.ruff.uno')

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = None  # localhost

class ProductionConfig(Config):
    DEBUG = False

# Select config based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}

def get_config():
    env = os.getenv('FLASK_ENV', 'production')
    return config.get(env, config['default'])


# JobTread API Configuration
@dataclass
class JobTreadConfig:
    api_key: str
    base_url: str
    organization_id: str

JOBTREAD_CONFIG = JobTreadConfig(
    api_key=os.getenv('JOBTREAD_API_KEY', '22T9iRwLuuk7r7Q8Q4bkvrcW86EVnMUwN5'),
    base_url=os.getenv('JOBTREAD_API_BASE_URL', 'https://api.jobtread.com/pave'),
    organization_id=os.getenv('JOBTREAD_ORGANIZATION_ID', '22NQrV725Q3z')
)

# Phase Specs Job ID in JobTread (RES-02)
PHASE_SPECS_JOB_ID = os.getenv('PHASE_SPECS_JOB_ID', '22PAFPENQXz5')
