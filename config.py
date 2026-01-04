# config.py
class Config:
    SECRET_KEY = 'safelens_secret_key'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:2653@localhost:5432/Safelens_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Google OAuth
    GOOGLE_CLIENT_ID = 'dummy-client-id'
    GOOGLE_CLIENT_SECRET = 'dummy-client-secret'
    GOOGLE_DISCOVERY_URL = 'https://accounts.google.com/.well-known/openid-configuration'
    
    # Flask-Mail
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'your-email@gmail.com'
    MAIL_PASSWORD = 'your-app-password'
    MAIL_DEFAULT_SENDER = 'your-email@gmail.com'

# Export the variables for easy import
GOOGLE_CLIENT_ID = Config.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = Config.GOOGLE_CLIENT_SECRET
GOOGLE_DISCOVERY_URL = Config.GOOGLE_DISCOVERY_URL