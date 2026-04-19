from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_login import LoginManager, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import db, AdminUser

login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "60 per hour"])

def create_app(config_name='default'):
    # 配置 - 使用绝对路径
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, 'download_site.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{db_path}')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 安全配置：SECRET_KEY必须通过环境变量设置
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        print("WARNING: SECRET_KEY not set! Generate one with:")
        print("  python -c \"import secrets; print(secrets.token_hex(32))\"")
        print("Set it via: export SECRET_KEY=<your-secret-key>")
        secret_key = os.urandom(32).hex()
    app.config['SECRET_KEY'] = secret_key

    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads'))
    # 不限制文件大小，由前端 nginx 或反向代理限制
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 初始化扩展
    db.init_app(app)

    # CORS配置：允许的来源（支持多个，逗号分隔）
    # 生产环境应设置为你的公网IP或域名
    # 例如: export ALLOWED_ORIGINS="http://1.2.3.4:8080,https://example.com"
    allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*')
    if allowed_origins == '*':
        CORS(app)
    else:
        origins_list = [o.strip() for o in allowed_origins.split(',')]
        CORS(app, origins=origins_list, methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"])

    login_manager.init_app(app)
    login_manager.session_protection = 'strong'
    limiter.init_app(app)
    
    # 注册蓝图
    from app.api.admin import admin_bp
    from app.api.download import download_bp
    from app.api.auth import auth_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(download_bp)

    # 创建数据库表
    with app.app_context():
        from models import File, ShareLink, SystemConfig
        from app.models.config import Config
        db.create_all()
        Config.init_default_config()

    # 登录路由
    @login_manager.user_loader
    def load_user(user_id):
        return AdminUser.query.get(int(user_id))

    # 检查是否需要初始化设置
    def check_needs_setup():
        with app.app_context():
            return AdminUser.query.count() == 0

    # 初始化设置页面
    @app.route('/setup')
    def setup_page():
        if not check_needs_setup():
            return render_template('admin.html')
        return render_template('setup.html')

    # 安全头中间件
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        return response

    # 登录页面
    @app.route('/login')
    def login_page():
        if current_user.is_authenticated:
            return render_template('admin.html')
        return render_template('login.html')

    # 管理后台页面（需登录）
    @app.route('/admin')
    @login_required
    def admin_page():
        return render_template('admin.html')

    # 404错误处理
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': '接口不存在'}), 404
        return render_template('admin.html'), 404

    # 401错误处理 - 重定向到登录页
    @app.errorhandler(401)
    def unauthorized(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': '未授权，请先登录'}), 401
        return render_template('login.html'), 401

    # 429错误处理
    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({'success': False, 'message': '请求过于频繁，请稍后再试'}), 429

    return app
