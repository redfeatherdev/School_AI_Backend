from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pymysql

pymysql.install_as_MySQLdb()

app = Flask(__name__)
CORS(app, origins="*", allow_headers="*")

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root@localhost/schoolai'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

migrate = Migrate(app, db)

from app.api.auth import *
from app.api.course import *