"""
管理员认证相关路由
"""
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, AdminUser, is_password_strong
from app import limiter
import re

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/setup', methods=['POST'])
def setup():
    """初始化设置管理员账户"""
    # 检查是否已存在管理员
    if AdminUser.query.count() > 0:
        return jsonify({'success': False, 'message': '系统已初始化'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请提供账户信息'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    errors = {}
    
    # 验证用户名
    if not username:
        errors['username'] = '用户名不能为空'
    elif len(username) < 3 or len(username) > 30:
        errors['username'] = '用户名长度应为3-30个字符'
    elif not re.match(r'^[\w_]+$', username):
        errors['username'] = '用户名只能包含字母、数字、下划线'
    elif AdminUser.query.filter_by(username=username).first():
        errors['username'] = '用户名已存在'
    
    # 验证密码
    if not password:
        errors['password'] = '密码不能为空'
    else:
        strong, msg = is_password_strong(password)
        if not strong:
            errors['password'] = msg
    
    if errors:
        return jsonify({'success': False, 'message': '请修正以下错误', 'errors': errors}), 400
    
    # 创建管理员账户
    admin = AdminUser(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '管理员账户创建成功'})


@auth_bp.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """管理员登录接口"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请提供用户名和密码'}), 400
    
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
    
    # 检查用户名格式（防XSS）
    if not re.match(r'^[\w_]{3,30}$', username):
        return jsonify({'success': False, 'message': '用户名格式不正确'}), 400
    
    admin = AdminUser.query.filter_by(username=username, is_active=True).first()
    
    if not admin:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
    
    success, message = admin.check_password(password)
    
    if not success:
        return jsonify({'success': False, 'message': message}), 401
    
    login_user(admin, remember=True)
    
    return jsonify({
        'success': True,
        'message': '登录成功',
        'data': admin.to_dict()
    })


@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """管理员登出接口"""
    logout_user()
    return jsonify({'success': True, 'message': '已退出登录'})


@auth_bp.route('/api/auth/check', methods=['GET'])
def check_login():
    """检查登录状态"""
    if current_user.is_authenticated:
        return jsonify({
            'success': True,
            'logged_in': True,
            'user': current_user.to_dict()
        })
    
    # 检查是否需要初始化
    needs_setup = AdminUser.query.count() == 0
    return jsonify({
        'success': True,
        'logged_in': False,
        'needs_setup': needs_setup
    })


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码接口"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请提供密码信息'}), 400
    
    new_password = data.get('new_password', '')

    if not new_password:
        return jsonify({'success': False, 'message': '密码不能为空'}), 400

    # 检查新密码强度
    strong, msg = is_password_strong(new_password)
    if not strong:
        return jsonify({'success': False, 'message': f'新密码强度不足: {msg}'}), 400

    try:
        current_user.set_password(new_password)
        db.session.commit()
        return jsonify({'success': True, 'message': '密码修改成功'})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@auth_bp.route('/api/auth/change-username', methods=['POST'])
@login_required
def change_username():
    """修改用户名接口"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': '请提供用户名信息'}), 400
    
    new_username = data.get('new_username', '').strip()

    if not new_username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400

    # 验证新用户名格式
    if len(new_username) < 3 or len(new_username) > 30:
        return jsonify({'success': False, 'message': '用户名长度应为3-30个字符'}), 400
    if not re.match(r'^[\w_]+$', new_username):
        return jsonify({'success': False, 'message': '用户名只能包含字母、数字、下划线'}), 400

    # 检查新用户名是否已被占用
    if AdminUser.query.filter_by(username=new_username).first() and new_username != current_user.username:
        return jsonify({'success': False, 'message': '用户名已被占用'}), 400

    # 检查新用户名与旧用户名相同
    if new_username == current_user.username:
        return jsonify({'success': False, 'message': '新用户名不能与旧用户名相同'}), 400
    
    current_user.username = new_username
    db.session.commit()
    
    return jsonify({'success': True, 'message': '用户名修改成功', 'data': current_user.to_dict()})
