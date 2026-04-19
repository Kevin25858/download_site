from flask import request
from app.models.config import Config


def get_public_url():
    """
    获取公网地址
    
    如果配置了public_url则返回配置值，否则返回request.host_url
    用于生成分享链接时构建完整URL
    
    Returns:
        str: 公网访问地址（以/结尾）
    """
    # 从数据库获取配置的公网地址
    configured_url = Config.get(Config.KEY_PUBLIC_URL, '')
    
    if configured_url and configured_url.strip():
        # 确保URL以/结尾
        url = configured_url.strip()
        if not url.endswith('/'):
            url += '/'
        return url
    
    # 如果没有配置，使用当前请求的host_url
    if request:
        return request.host_url
    
    # 如果不在请求上下文中，返回空字符串
    return ''


def build_share_url(path):
    """
    构建完整的分享链接URL
    
    Args:
        path: 相对路径（如 'share/abc123'）
        
    Returns:
        str: 完整的URL
    """
    base_url = get_public_url()
    
    # 确保path不以/开头
    if path.startswith('/'):
        path = path[1:]
    
    return base_url + path
