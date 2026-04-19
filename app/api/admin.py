from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
import os
import uuid as uuid_module
import secrets
import string
from datetime import datetime, timedelta
from models import db, File, ShareLink
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.models.config import Config

admin_bp = Blueprint('admin', __name__)

# 允许的文件类型白名单
ALLOWED_EXTENSIONS = {
    # 文档
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf', 'odt',
    # 图片
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico', 'tiff',
    # 音视频
    'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma',
    'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm',
    # 压缩包
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz',
    # 代码
    'py', 'js', 'html', 'css', 'json', 'xml', 'java', 'c', 'cpp', 'h', 'go', 'rs', 'php', 'rb', 'swift', 'kt',
    # 其他
    'exe', 'dmg', 'app', 'apk', 'msi',
}

def generate_unique_filename(original_filename):
    """生成唯一的文件名"""
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_name = f"{uuid_module.uuid4().hex}"
    if ext:
        unique_name = f"{unique_name}.{ext}"
    return unique_name

def is_allowed_file(filename):
    """检查文件类型是否允许"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

# 1. 文件上传接口 POST /api/admin/upload
@admin_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """
    文件上传接口
    支持 multipart/form-data 格式
    表单字段名: file
    """
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'message': '没有文件被上传'
        }), 400
    
    file = request.files['file']

    # 检查文件名是否为空
    if file.filename == '':
        return jsonify({
            'success': False,
            'message': '文件名不能为空'
        }), 400

    # 检查文件类型是否允许
    if not is_allowed_file(file.filename):
        return jsonify({
            'success': False,
            'message': f'不支持的文件类型，仅允许: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
        }), 400

    # 保存文件
    original_filename = secure_filename(file.filename)
    unique_filename = generate_unique_filename(original_filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    
    try:
        # 保存文件到磁盘
        file.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 创建数据库记录
        new_file = File(
            filename=unique_filename,
            original_filename=original_filename,
            file_size=file_size,
            file_path=file_path,
            mime_type=file.content_type
        )
        
        db.session.add(new_file)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '文件上传成功',
            'data': {
                'file_id': new_file.id,
                'filename': new_file.filename,
                'original_filename': new_file.original_filename,
                'file_size': new_file.file_size,
                'mime_type': new_file.mime_type,
                'created_at': new_file.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        # 如果保存失败，删除已上传的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'文件上传失败: {str(e)}'
        }), 500

# 2. 文件列表接口 GET /api/admin/files
@admin_bp.route('/files', methods=['GET'])
@login_required
def get_files():
    """
    获取文件列表
    支持分页参数: page, per_page
    默认: page=1, per_page=20
    """
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 限制每页最大数量
        if per_page > 100:
            per_page = 100
        
        # 查询文件列表
        pagination = File.query.order_by(File.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        files = pagination.items
        
        return jsonify({
            'success': True,
            'data': {
                'files': [file.to_dict() for file in files],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取文件列表失败: {str(e)}'
        }), 500

# 3. 生成分享链接接口 POST /api/admin/share
@admin_bp.route('/share', methods=['POST'])
@login_required
def create_share_link():
    """
    生成分享链接
    请求参数: file_id (单文件) 或 file_ids (多文件/文件夹), max_downloads (可选), expires_in_hours (可选)
    """
    import zipfile

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': '请求体不能为空'
            }), 400

        file_ids = data.get('file_ids', [])
        single_file_id = data.get('file_id')
        max_downloads = data.get('max_downloads')
        expires_in_hours = data.get('expires_in_hours')

        # 如果有单文件ID，转为列表
        if single_file_id and not file_ids:
            file_ids = [single_file_id]

        if not file_ids:
            return jsonify({
                'success': False,
                'message': '请选择要分享的文件'
            }), 400

        # 验证所有文件
        files = []
        for fid in file_ids:
            f = File.query.get(fid)
            if not f:
                return jsonify({
                    'success': False,
                    'message': f'文件不存在 (ID: {fid})'
                }), 404
            files.append(f)

        # 计算过期时间
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=int(expires_in_hours))

        # 生成6位数字下载密码
        download_password = ''.join(secrets.choice(string.digits) for _ in range(6))

        is_folder = len(files) > 1
        share_file = files[0]

        # 如果是多文件，创建zip
        if is_folder:
            folder_name = '分享文件夹'
            zip_filename = f"{uuid_module.uuid4().hex}.zip"
            zip_path = os.path.join(current_app.config['UPLOAD_FOLDER'], zip_filename)

            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for f in files:
                        if os.path.exists(f.file_path):
                            zf.write(f.file_path, f.original_filename)
                        else:
                            current_app.logger.warning(f'文件不存在: {f.file_path}')

                # 创建虚拟文件记录
            except Exception as zip_err:
                current_app.logger.error(f'创建zip失败: {zip_err}')
                return jsonify({
                    'success': False,
                    'message': '创建文件夹分享失败'
                }), 500

            folder_file = File(
                filename=zip_filename,
                original_filename=folder_name + '.zip',
                file_size=os.path.getsize(zip_path),
                file_path=zip_path,
                mime_type='application/zip'
            )
            db.session.add(folder_file)
            db.session.flush()
            share_file = folder_file

        # 创建分享链接
        share_link = ShareLink(
            file_id=share_file.id,
            is_folder=is_folder,
            max_downloads=max_downloads,
            expires_at=expires_at
        )
        share_link.set_password(download_password)

        db.session.add(share_link)
        db.session.commit()

        # 构建完整的分享链接URL
        base_url = request.host_url.rstrip('/')
        full_share_url = f"{base_url}/d/{share_link.token}"

        return jsonify({
            'success': True,
            'message': '分享链接创建成功',
            'data': {
                'share_id': share_link.id,
                'token': share_link.token,
                'share_url': full_share_url,
                'download_password': download_password,
                'has_password': True,
                'is_folder': is_folder,
                'file': share_file.to_dict(),
                'file_count': len(files) if is_folder else 1,
                'max_downloads': share_link.max_downloads,
                'expires_at': share_link.expires_at.isoformat() if share_link.expires_at else None,
                'created_at': share_link.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'创建分享链接失败: {str(e)}'
        }), 500

# 4. 删除文件接口 DELETE /api/admin/files/<id>
@admin_bp.route('/files/<int:file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    """
    删除文件
    删除数据库记录、物理文件和关联的分享链接
    """
    try:
        # 查找文件
        file = File.query.get(file_id)
        
        if not file:
            return jsonify({
                'success': False,
                'message': '文件不存在'
            }), 404
        
        file_path = file.file_path
        original_filename = file.original_filename
        
        # 删除数据库记录（关联的分享链接会自动删除，因为设置了 cascade）
        db.session.delete(file)
        db.session.commit()
        
        # 删除物理文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                # 文件删除失败但数据库记录已删除，记录警告
                current_app.logger.warning(f'删除物理文件失败 {file_path}: {e}')
        
        return jsonify({
            'success': True,
            'message': f'文件 "{original_filename}" 删除成功'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'删除文件失败: {str(e)}'
        }), 500

# 5. 获取分享链接列表接口 GET /api/admin/shares
@admin_bp.route('/shares', methods=['GET'])
@login_required
def get_share_links():
    """
    获取所有分享链接列表
    支持分页参数: page, per_page
    包含关联的文件信息
    """
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 限制每页最大数量
        if per_page > 100:
            per_page = 100
        
        # 查询分享链接列表
        pagination = ShareLink.query.order_by(ShareLink.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        share_links = pagination.items
        
        return jsonify({
            'success': True,
            'data': {
                'shares': [share.to_dict(include_file=True) for share in share_links],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': pagination.total,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取分享链接列表失败: {str(e)}'
        }), 500

# 额外的接口：删除分享链接
@admin_bp.route('/shares/<int:share_id>', methods=['DELETE'])
@login_required
def delete_share_link(share_id):
    """
    删除分享链接
    """
    try:
        share_link = ShareLink.query.get(share_id)
        
        if not share_link:
            return jsonify({
                'success': False,
                'message': '分享链接不存在'
            }), 404
        
        db.session.delete(share_link)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '分享链接删除成功'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'删除分享链接失败: {str(e)}'
        }), 500


# 6. 获取系统配置接口 GET /api/admin/config
@admin_bp.route('/config', methods=['GET'])
@login_required
def get_config():
    """
    获取系统配置
    返回公网地址等配置信息
    """
    try:
        public_url = Config.get(Config.KEY_PUBLIC_URL, '')
        
        return jsonify({
            'success': True,
            'data': {
                'public_url': public_url
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取配置失败: {str(e)}'
        }), 500


# 7. 保存系统配置接口 POST /api/admin/config
@admin_bp.route('/config', methods=['POST'])
@login_required
def save_config():
    """
    保存系统配置
    请求参数: public_url (可选)
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': '请求体不能为空'
            }), 400
        
        public_url = data.get('public_url', '')
        
        # 保存配置
        Config.set(Config.KEY_PUBLIC_URL, public_url, '公网访问地址，用于生成分享链接')
        
        return jsonify({
            'success': True,
            'message': '配置保存成功',
            'data': {
                'public_url': public_url
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'保存配置失败: {str(e)}'
        }), 500
