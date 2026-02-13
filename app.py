from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from models import db, User, Record
import os

app = Flask(__name__)

# 配置
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///accounting.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 创建数据库表
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 检查用户是否已存在
        user = User.query.filter_by(username=username).first()
        if user:
            flash('用户名已存在', 'danger')
            return redirect(url_for('register'))
        
        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('邮箱已注册', 'danger')
            return redirect(url_for('register'))
        
        # 创建新用户
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('注册成功！请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/api/records', methods=['GET'])
@login_required
def get_records():
    # 获取筛选参数
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Record.query.filter_by(user_id=current_user.id)
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Record.date >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        # 将结束日期设置为当天的23:59:59
        end = end.replace(hour=23, minute=59, second=59)
        query = query.filter(Record.date <= end)
    
    records = query.order_by(Record.date.desc()).all()
    
    # 计算统计数据
    total_income = sum(r.amount for r in records if r.type == 'income')
    total_expense = sum(r.amount for r in records if r.type == 'expense')
    balance = total_income - total_expense
    
    records_data = [{
        'id': r.id,
        'type': r.type,
        'amount': r.amount,
        'category': r.category,
        'description': r.description,
        'date': r.date.strftime('%Y-%m-%d')
    } for r in records]
    
    return jsonify({
        'records': records_data,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance
    })

@app.route('/api/records', methods=['POST'])
@login_required
def add_record():
    data = request.json
    
    record = Record(
        user_id=current_user.id,
        type=data['type'],
        amount=float(data['amount']),
        category=data['category'],
        description=data.get('description', ''),
        date=datetime.strptime(data['date'], '%Y-%m-%d')
    )
    
    db.session.add(record)
    db.session.commit()
    
    return jsonify({'message': '记录添加成功', 'id': record.id}), 201

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@login_required
def delete_record(record_id):
    record = Record.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(record)
    db.session.commit()
    
    return jsonify({'message': '记录删除成功'})

@app.route('/api/records/<int:record_id>', methods=['PUT'])
@login_required
def update_record(record_id):
    record = Record.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    data = request.json
    
    record.type = data.get('type', record.type)
    record.amount = float(data.get('amount', record.amount))
    record.category = data.get('category', record.category)
    record.description = data.get('description', record.description)
    record.date = datetime.strptime(data.get('date', record.date.strftime('%Y-%m-%d')), '%Y-%m-%d')
    
    db.session.commit()
    
    return jsonify({'message': '记录更新成功'})

if __name__ == '__main__':
    app.run(debug=True)
