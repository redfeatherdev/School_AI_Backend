from flask import request, jsonify
from datetime import datetime
from functools import wraps
from app.config import JWT_SECRET_KEY

import jwt

def encode_auth_token(payload):
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            'iat': datetime.datetime.utcnow(),
            'sub': payload
        }

        return jwt.encode(
            payload,
            JWT_SECRET_KEY,
            algorithm='HS256'
        )
    except Exception as e:
        return e

def decode_auth_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return 'Your session is expired. Please login again'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please login again'

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            token = request.headers['Authorization']

        if not token:
            return jsonify({'msg': 'Token is missing'}), 401
        
        try:
            data = decode_auth_token(token)
            if isinstance(data, str):
                return jsonify({'msg': data}), 401
            request.user = data['sub']
        except Exception as e:
            return jsonify({'msg': str(e)}), 401
        
        return f(*args, **kwargs)
    return decorated