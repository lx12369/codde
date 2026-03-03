from functools import wraps
from flask import request, jsonify, g
from .auth import decode_token


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                'success': False,
                'message': '缺少身份令牌',
                'code': 401
            }), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({
                'success': False,
                'message': '身份令牌无效或已过期',
                'code': 401
            }), 401
        
        user_id = payload.get('sub')
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)

        g.current_user_id = user_id
        g.current_user = payload
        
        return f(*args, **kwargs)
    
    return decorated
