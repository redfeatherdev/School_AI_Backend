from flask import request, jsonify
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, db
from app.models import User
from app.config import JWT_SECRET_KEY

import jwt

@app.route("/api/v1/auth/signin", methods=["POST"])
def signin():
    if (
        request.method == "POST"
        and "email" in request.form
        and "password" in request.form
    ):
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({"msg": "Email address not found"}), 401

        if not check_password_hash(user.password, password):
            return jsonify({"msg": "Incorrect password"}), 401

        try:
            payload = {
                'exp': datetime.utcnow() + timedelta(hours=1),
                'iat': datetime.utcnow(),
                'sub': user.id
            }

            token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

            return jsonify({
                "msg": "Login successful",
                "token": token,
                "user": user.to_dict()
            }), 200

        except Exception as e:
            print(f"Token generation failed: {e}")
            return jsonify({"msg": "Token generation failed"}), 500

    else:
        return jsonify({"status": 400, "message": "Missing fields"}), 400

@app.route("/api/v1/auth/signup", methods=["POST"])
def signup():
    if (
        request.method == "POST"
        and "name" in request.form
        and "email" in request.form
        and "password" in request.form
    ):
        name = request.form["name"]
        email = request.form["email"]
        role = request.form['role']
        password = generate_password_hash(request.form["password"])

        existing_user = User.query.filter_by(email=email).first()
        
        if existing_user:
            return jsonify({"msg": "User already registered."}), 409

        new_user = User(name=name, email=email, role=role, password=password)
        
        try:
            db.session.add(new_user)
            db.session.commit()

            return jsonify({"msg": "User Registered successfully"}), 200
        except Exception as e:
            print(f"Database operation failed due to {e}")
            db.session.rollback()
            return jsonify({"msg": "Database Error"}), 400
    else:
        return jsonify({"status": 400, "message": "Missing fields"}), 400
