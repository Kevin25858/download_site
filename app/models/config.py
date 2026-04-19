import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from models import db
from datetime import datetime


class Config(db.Model):
    """系统配置模型 - key-value存储"""
    __tablename__ = 'configs'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 默认配置键名
    KEY_PUBLIC_URL = 'public_url'
    
    def __repr__(self):
        return f'<Config {self.key}={self.value}>'
    
    @classmethod
    def get(cls, key, default=None):
        """获取配置值"""
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default
    
    @classmethod
    def set(cls, key, value, description=None):
        """设置配置值"""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = cls(key=key, value=value, description=description)
            db.session.add(config)
        db.session.commit()
        return config
    
    @classmethod
    def init_default_config(cls):
        """初始化默认配置"""
        # 初始化 public_url 为空字符串
        existing = cls.query.filter_by(key=cls.KEY_PUBLIC_URL).first()
        if not existing:
            cls.set(
                key=cls.KEY_PUBLIC_URL,
                value='',
                description='公网访问地址，用于生成分享链接'
            )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
