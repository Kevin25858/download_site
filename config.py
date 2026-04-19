"""
配置文件
包含数据库连接、文件上传限制等配置项
"""

import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """基础配置类"""
    
    # 密钥配置（用于 session、CSRF 等）
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(BASE_DIR, "app.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    # 不限制文件大小，由前端 nginx 或反向代理限制
    
    # 允许的文件扩展名（可根据需要调整）
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', '7z',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'mp3', 'mp4',
        'avi', 'mov', 'mkv', 'exe', 'msi', 'apk', 'ipa'
    }
    
    # 公网地址配置键名
    PUBLIC_URL_KEY = 'public_url'
    
    # 分享链接默认有效期（天）
    SHARE_LINK_EXPIRE_DAYS = 7
    
    # 分页配置
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # 生产环境必须使用环境变量设置密钥
    SECRET_KEY = os.environ.get('SECRET_KEY')


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# 配置映射字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """获取配置对象
    
    Args:
        env: 环境名称，可选值为 'development', 'production', 'testing'
        
    Returns:
        Config: 配置类实例
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
