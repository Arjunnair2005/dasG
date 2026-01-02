from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feemaster.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)
db = SQLAlchemy(app)

# Models
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    course = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(15))
    total_dues = db.Column(db.Float, default=0.0)
    payments = db.relationship('Payment', backref='student', lazy=True)

class FeeStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    fee_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    method = db.Column(db.String(50), default='online')
    receipt_no = db.Column(db.String(50), unique=True)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

# Create tables
with app.app_context():
    db.create_all()
    
    # Seed sample data
    if not Admin.query.first():
        admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()
    
    if not Student.query.first():
        student = Student(roll_no='BCA001', name='Arjun Murlidharan Nair', 
                         course='BCA 3rd Year', email='arjun@example.com', total_dues=15000)
        db.session.add(student)
        db.session.commit()

# Routes
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if data['username'] == 'admin' and check_password_hash(Admin.query.first().password_hash, data['password']):
        return jsonify({'token': 'admin-token', 'role': 'admin'})
    elif Student.query.filter_by(roll_no=data['username']).first():
        return jsonify({'token': 'student-token', 'role': 'student'})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/students', methods=['GET'])
def get_students():
    students = Student.query.all()
    return jsonify([{
        'id': s.id, 'roll_no': s.roll_no, 'name': s.name, 
        'course': s.course, 'total_dues': s.total_dues
    } for s in students])

@app.route('/api/students/<roll_no>', methods=['GET'])
def get_student(roll_no):
    student = Student.query.filter_by(roll_no=roll_no).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    payments = [{'amount': p.amount, 'date': p.payment_date.isoformat()} for p in student.payments]
    return jsonify({
        'roll_no': student.roll_no,
        'name': student.name,
        'course': student.course,
        'total_dues': student.total_dues,
        'payments': payments
    })

@app.route('/api/payments', methods=['POST'])
def make_payment():
    data = request.json
    student = Student.query.filter_by(roll_no=data['roll_no']).first()
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    
    payment = Payment(
        student_id=student.id,
        amount=data['amount'],
        method=data['method'],
        receipt_no=f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    db.session.add(payment)
    student.total_dues -= data['amount']
    db.session.commit()
    
    return jsonify({
        'success': True,
        'receipt_no': payment.receipt_no,
        'new_balance': student.total_dues
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total_students = Student.query.count()
    total_collected = db.session.query(db.func.sum(Payment.amount)).scalar() or 0
    defaulters = Student.query.filter(Student.total_dues > 0).count()
    total_invoices = FeeStructure.query.count()
    
    return jsonify({
        'total_students': total_students,
        'total_collected': float(total_collected),
        'defaulters': defaulters,
        'total_invoices': total_invoices
    })

@app.route('/api/recent-payments', methods=['GET'])
def recent_payments():
    payments = Payment.query.order_by(Payment.payment_date.desc()).limit(10).all()
    return jsonify([{
        'student_roll': p.student.roll_no,
        'student_name': p.student.name,
        'amount': p.amount,
        'date': p.payment_date.isoformat()
    } for p in payments])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
