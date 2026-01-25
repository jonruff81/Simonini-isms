"""
Simonini-isms Flask Application Factory
"""
import logging
import os
from flask import Flask
from flask_cors import CORS

def create_app(config_name=None):
    """Application factory"""
    app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')

    from app.config import config
    app.config.from_object(config.get(config_name, config['default']))

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Enable CORS
    CORS(app, supports_credentials=True, origins=[
        'https://isms.ruff.uno',
        'https://ash.ruff.uno',
        'http://localhost:5000',
        'http://localhost:8082'
    ])

    # Register blueprints
    from app.api.auth import auth_bp
    from app.api.phases import phases_bp
    from app.api.rules import rules_bp
    from app.api.bookmarks import bookmarks_bp
    from app.api.highlights import highlights_bp
    from app.api.notes import notes_bp
    from app.api.share import share_bp
    from app.api.phase_specs import phase_specs_bp
    from app.api.spec_reference import spec_reference_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(phases_bp, url_prefix='/api/phases')
    app.register_blueprint(rules_bp, url_prefix='/api/rules')
    app.register_blueprint(bookmarks_bp, url_prefix='/api/bookmarks')
    app.register_blueprint(highlights_bp, url_prefix='/api/highlights')
    app.register_blueprint(notes_bp, url_prefix='/api/notes')
    app.register_blueprint(share_bp, url_prefix='/api/share')
    app.register_blueprint(phase_specs_bp)
    app.register_blueprint(spec_reference_bp)

    # Register main routes
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'app': 'simonini-isms'}

    return app
