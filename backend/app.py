from flask import Flask, jsonify
from flask_cors import CORS
from flask_restful import Api
from models import db, init_db
from config import config


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    CORS(app, resources={
        r'/api/*': {
            'origins': '*',
            'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            'allow_headers': ['Content-Type', 'Authorization']
        }
    })
    
    db.init_app(app)
    
    api = Api(app, prefix='/api')
    
    register_routes(app)
    
    register_error_handlers(app)
    
    init_db(app)
    
    return app


def register_routes(app):
    from routes.auth import auth_bp
    from routes.customers import customers_bp
    from routes.employees import employees_bp
    from routes.transactions import transactions_bp
    from routes.activities import activities_bp
    from routes.billing import billing_bp
    from routes.active_timers import active_timers_bp
    from routes.dashboard import dashboard_bp
    from routes.data import data_bp
    from routes.logs import logs_bp
    from routes.bead_inventory import bead_inventory_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(customers_bp, url_prefix='/api/customers')
    app.register_blueprint(employees_bp, url_prefix='/api/employees')
    app.register_blueprint(transactions_bp, url_prefix='/api/transactions')
    app.register_blueprint(activities_bp, url_prefix='/api/activities')
    app.register_blueprint(billing_bp, url_prefix='/api')
    app.register_blueprint(active_timers_bp, url_prefix='/api/active-timers')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(data_bp, url_prefix='/api/data')
    app.register_blueprint(logs_bp, url_prefix='/api/logs')
    app.register_blueprint(bead_inventory_bp, url_prefix='/api/bead-inventory')


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': '请求参数错误', 'message': str(error)}), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': '未授权访问', 'message': str(error)}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': '禁止访问', 'message': str(error)}), 403
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '资源不存在', 'message': str(error)}), 404
    
    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({'error': '服务器内部错误', 'message': str(error)}), 500


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
