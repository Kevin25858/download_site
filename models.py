"""
数据库模型定义
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
import secrets
import string
import re

db = SQLAlchemy()


def is_password_strong(password):
    """
    检查密码强度
    要求：至少8位，包含大小写字母和数字
    """
    if len(password) < 8:
        return False, "密码长度至少8位"
    if not re.search(r'[A-Z]', password):
        return False, "密码必须包含大写字母"
    if not re.search(r'[a-z]', password):
        return False, "密码必须包含小写字母"
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"
    return True, "密码强度合格"


class AdminUser(db.Model, UserMixin):
    """管理员用户模型"""
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        strong, _ = is_password_strong(password)
        if not strong:
            raise ValueError("密码强度不足")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return False, "账户已被锁定，请稍后再试"
        if not check_password_hash(self.password_hash, password):
            self.login_attempts += 1
            if self.login_attempts >= 5:
                self.locked_until = datetime.utcnow() + timedelta(minutes=30)
                self.login_attempts = 0
            db.session.commit()
            return False, "密码错误"
        if self.login_attempts > 0 or self.locked_until:
            self.login_attempts = 0
            self.locked_until = None
        self.last_login = datetime.utcnow()
        db.session.commit()
        return True, "登录成功"

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


def generate_token(length=32):
    """生成随机token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class File(db.Model):
    """文件模型"""
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False, default=0)
    file_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联关系
    share_links = db.relationship('ShareLink', backref='file', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        active_share = None
        for share in self.share_links:
            if share.is_valid():
                active_share = {
                    'token': share.token,
                    'share_url': f'/d/{share.token}',
                    'download_count': share.download_count,
                    'max_downloads': share.max_downloads,
                    'expires_at': share.expires_at.isoformat() if share.expires_at else None
                }
                break
        return {
            'id': self.id,
            'uuid': self.uuid,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'has_share': len(self.share_links) > 0,
            'active_share': active_share
        }

    def get_formatted_size(self):
        """获取格式化后的文件大小"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


class ShareLink(db.Model):
    """分享链接模型"""
    __tablename__ = 'share_links'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=generate_token)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)
    is_folder = db.Column(db.Boolean, default=False)  # 是否为文件夹分享
    download_count = db.Column(db.Integer, default=0)
    max_downloads = db.Column(db.Integer, nullable=True)  # null表示无限制
    expires_at = db.Column(db.DateTime, nullable=True)  # null表示永不过期
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_file=False):
        data = {
            'id': self.id,
            'token': self.token,
            'file_id': self.file_id,
            'is_folder': self.is_folder,
            'has_password': bool(self.password_hash),
            'download_count': self.download_count,
            'max_downloads': self.max_downloads,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_file and self.file:
            data['file'] = self.file.to_dict()
        return data

    def set_password(self, password):
        """设置下载密码"""
        if password:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证下载密码"""
        if not self.password_hash:
            return True
        return check_password_hash(self.password_hash, password)

    def is_valid(self):
        """检查链接是否有效"""
        if not self.is_active:
            return False

        # 检查是否过期
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False

        # 检查下载次数
        if self.max_downloads is not None and self.download_count >= self.max_downloads:
            return False

        return True

    def increment_download_count(self):
        """增加下载计数"""
        self.download_count += 1
        db.session.commit()


class SystemConfig(db.Model):
    """系统配置模型"""
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        """获取配置值"""
        config = SystemConfig.query.filter_by(key=key).first()
        return config.value if config else default

    @staticmethod
    def set(key, value):
        """设置配置值"""
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = value
        else:
            config = SystemConfig(key=key, value=value)
            db.session.add(config)
        db.session.commit()
