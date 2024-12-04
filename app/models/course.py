from app import db
from datetime import datetime, UTC

class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    prompt = db.Column(db.String(255), nullable=False)
    course = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    def __repr__(self):
        return f"<Course {self.id}>"
