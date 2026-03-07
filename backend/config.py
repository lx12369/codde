import os

from dotenv import load_dotenv

from db_runtime import get_sqlalchemy_engine_options, resolve_database_uri

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    SQLALCHEMY_DATABASE_URI = resolve_database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = get_sqlalchemy_engine_options(SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 32400))
    JWT_REMEMBER_TOKEN_EXPIRES = int(os.environ.get('JWT_REMEMBER_TOKEN_EXPIRES', 604800))
    JWT_REFRESH_TOKEN_EXPIRES = int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES', 2592000))

    AMAP_WEATHER_KEY = os.environ.get('AMAP_WEATHER_KEY', '')
    AMAP_WEATHER_API_HOST = os.environ.get('AMAP_WEATHER_API_HOST', 'https://restapi.amap.com')
    AMAP_WEATHER_LOCATION = os.environ.get('AMAP_WEATHER_LOCATION', '宁波市鄞州区下应街道')
    AMAP_WEATHER_ADCODE = os.environ.get('AMAP_WEATHER_ADCODE', '')
    AMAP_WEATHER_CITY_LABEL = os.environ.get('AMAP_WEATHER_CITY_LABEL', '宁波市鄞州区下应街道')
    AMAP_WEATHER_TIMEOUT_SECONDS = int(os.environ.get('AMAP_WEATHER_TIMEOUT_SECONDS', 5))
    AMAP_WEATHER_CACHE_SECONDS = int(os.environ.get('AMAP_WEATHER_CACHE_SECONDS', 300))
    AMAP_WEATHER_MONTHLY_QUOTA = int(os.environ.get('AMAP_WEATHER_MONTHLY_QUOTA', 5000))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    SQLALCHEMY_ENGINE_OPTIONS = {}


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
