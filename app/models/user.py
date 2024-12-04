from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    
    def to_dict(self):
        return {
            'name': self.name,
            'email': self.email,
            'role': self.role
        }
