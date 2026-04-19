"""
用户下载相关路由
"""
import os
import re
from flask import Blueprint, request, jsonify, send_file, render_template, current_app, session
from werkzeug.http import http_date
import mimetypes

from models import db, File, ShareLink
from app.models.config import Config
from app import limiter


download_bp = Blueprint('download', __name__)


def get_base_url():
    """获取基础URL（支持FRP配置）"""
    external_url = Config.get(Config.KEY_PUBLIC_URL)
    if external_url:
        return external_url.rstrip('/')
    return request.host_url.rstrip('/')


def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes is None or size_bytes == 0:
        return "0 B"

    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


@download_bp.route('/api/download/<token>', methods=['GET'])
@limiter.limit("30 per minute")
def get_download_info(token):
    """
    获取下载页面数据接口
    根据token查找ShareLink，返回文件信息
    """
    # 查找分享链接
    share_link = ShareLink.query.filter_by(token=token).first()

    # 如果token无效返回404
    if not share_link:
        return jsonify({
            'success': False,
            'error': 'Not found',
            'message': '无效的下载链接'
        }), 404

    # 检查链接是否有效
    if not share_link.is_valid():
        return jsonify({
            'success': False,
            'error': 'Invalid link',
            'message': '链接已过期或已达到下载次数限制'
        }), 410

    # 获取关联的文件
    file = share_link.file
    if not file:
        return jsonify({
            'success': False,
            'error': 'File not found',
            'message': '文件不存在'
        }), 404

    # 检查文件是否存在
    if not os.path.exists(file.file_path):
        return jsonify({
            'success': False,
            'error': 'File not found',
            'message': '文件已被删除'
        }), 404

    # 返回文件信息
    return jsonify({
        'success': True,
        'data': {
            'token': token,
            'filename': file.original_filename or file.filename,
            'file_size': file.file_size,
            'file_size_formatted': format_file_size(file.file_size),
            'mime_type': file.mime_type or 'application/octet-stream',
            'download_count': share_link.download_count,
            'max_downloads': share_link.max_downloads,
            'expires_at': share_link.expires_at.isoformat() if share_link.expires_at else None,
            'created_at': share_link.created_at.isoformat() if share_link.created_at else None,
            'has_password': bool(share_link.password_hash)
        }
    })


@download_bp.route('/api/download/<token>/verify', methods=['POST'])
def verify_password(token):
    """
    验证下载密码接口
    """
    share_link = ShareLink.query.filter_by(token=token).first()

    if not share_link:
        return jsonify({
            'success': False,
            'message': '链接无效'
        }), 404

    if not share_link.is_valid():
        return jsonify({
            'success': False,
            'message': '链接已过期或达到下载次数限制'
        }), 410

    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': '请提供密码'
        }), 400

    password = data.get('password', '')

    if share_link.check_password(password):
        # 设置session标记已验证
        session[f'verified_{token}'] = True
        return jsonify({
            'success': True,
            'message': '验证成功'
        })
    else:
        return jsonify({
            'success': False,
            'message': '密码错误'
        }), 401


@download_bp.route('/api/download/<token>/file', methods=['GET'])
def download_file(token):
    """
    文件下载接口
    验证token有效性，使用send_file发送文件，支持断点续传
    """
    # 查找分享链接
    share_link = ShareLink.query.filter_by(token=token).first()

    # 验证token有效性
    if not share_link:
        return jsonify({
            'success': False,
            'error': 'Not found',
            'message': '无效的下载链接'
        }), 404

    # 检查链接是否有效
    if not share_link.is_valid():
        return jsonify({
            'success': False,
            'error': 'Invalid link',
            'message': '链接已过期或已达到下载次数限制'
        }), 410

    # 如果有密码，检查是否已验证
    if share_link.password_hash and not session.get(f'verified_{token}'):
        return jsonify({
            'success': False,
            'error': 'Password required',
            'message': '请先验证密码'
        }), 401

    # 获取关联的文件
    file = share_link.file
    if not file:
        return jsonify({
            'success': False,
            'error': 'File not found',
            'message': '文件不存在'
        }), 404

    # 检查文件是否存在
    if not os.path.exists(file.file_path):
        return jsonify({
            'success': False,
            'error': 'File not found',
            'message': '文件已被删除'
        }), 404

    # 获取文件信息
    file_path = file.file_path
    file_size = os.path.getsize(file_path)
    filename = file.original_filename or file.filename

    # 确定MIME类型
    mime_type = file.mime_type
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'

    # 处理Range请求（断点续传）
    range_header = request.headers.get('Range', None)

    if range_header:
        # 解析Range头
        # Range: bytes=start-end
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1

            # 验证范围
            if start >= file_size or end >= file_size or start > end:
                return jsonify({
                    'success': False,
                    'error': 'Invalid range',
                    'message': '请求的范围无效'
                }), 416

            # 计算内容长度
            content_length = end - start + 1

            # 打开文件并定位到起始位置
            def generate():
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    chunk_size = 8192
                    while remaining > 0:
                        read_size = min(chunk_size, remaining)
                        data = f.read(read_size)
                        if not data:
                            break
                        remaining -= len(data)
                        yield data

            # 更新下载计数
            share_link.increment_download_count()

            # 返回206 Partial Content
            response = current_app.response_class(
                generate(),
                status=206,
                mimetype=mime_type
            )
            response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response.headers['Content-Length'] = str(content_length)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.headers['Last-Modified'] = http_date(os.path.getmtime(file_path))

            return response

    # 完整文件下载
    # 更新下载计数
    share_link.increment_download_count()

    # 使用send_file发送文件
    response = send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )

    # 设置响应头
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Length'] = str(file_size)
    response.headers['Last-Modified'] = http_date(os.path.getmtime(file_path))

    return response


@download_bp.route('/d/<token>', methods=['GET'])
def download_page(token):
    """
    下载页面路由
    渲染下载页面模板，传递文件信息到前端
    """
    # 查找分享链接
    share_link = ShareLink.query.filter_by(token=token).first()

    # 如果token无效返回404页面
    if not share_link:
        return render_template('download_error.html',
                               error_title='链接无效',
                               error_message='您访问的下载链接不存在或已被删除'), 404

    # 检查链接是否有效
    if not share_link.is_valid():
        return render_template('download_error.html',
                               error_title='链接已失效',
                               error_message='该链接已过期或已达到下载次数限制'), 410

    # 获取关联的文件
    file = share_link.file
    if not file:
        return render_template('download_error.html',
                               error_title='文件不存在',
                               error_message='该链接关联的文件已被删除'), 404

    # 检查文件是否存在
    if not os.path.exists(file.file_path):
        return render_template('download_error.html',
                               error_title='文件已被删除',
                               error_message='该文件已被管理员删除'), 404

    # 准备文件信息
    file_info = {
        'token': token,
        'filename': file.original_filename or file.filename,
        'file_size': file.file_size,
        'file_size_formatted': format_file_size(file.file_size),
        'mime_type': file.mime_type or 'application/octet-stream',
        'download_count': share_link.download_count,
        'max_downloads': share_link.max_downloads,
        'expires_at': share_link.expires_at.isoformat() if share_link.expires_at else None,
        'created_at': share_link.created_at.isoformat() if share_link.created_at else None,
        'has_password': bool(share_link.password_hash),
        'api_url': f'/api/download/{token}',
        'download_url': f'/api/download/{token}/file'
    }

    # 渲染下载页面
    return render_template('download.html', file_info=file_info)
