#!/usr/bin/env python3
"""
文件分享下载站点启动脚本

用法:
    python run.py              # 默认在 0.0.0.0:5000 启动，debug模式
    python run.py --host 127.0.0.1 --port 8080 --no-debug
    python run.py -h           # 查看帮助
"""

import argparse
import os
import sys

# 添加项目根目录到Python路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import create_app


def main():
    """主函数：解析命令行参数并启动应用"""
    parser = argparse.ArgumentParser(
        description='文件分享下载站点',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                           # 默认配置启动
  python run.py --host 0.0.0.0 --port 80  # 指定主机和端口
  python run.py --no-debug                # 关闭调试模式
        """
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='服务器监听地址 (默认: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='服务器监听端口 (默认: 5000)'
    )
    
    parser.add_argument(
        '--no-debug',
        action='store_true',
        help='关闭调试模式 (默认开启)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='default',
        choices=['development', 'production', 'testing', 'default'],
        help='配置环境 (默认: default)'
    )
    
    args = parser.parse_args()
    
    # 创建应用实例
    app = create_app(config_name=args.config)
    
    # 设置调试模式
    debug_mode = not args.no_debug
    
    print(f"""
========================================
  文件分享下载站点已启动
========================================
  访问地址: http://{args.host}:{args.port}
  管理后台: http://{args.host}:{args.port}/admin
  调试模式: {'开启' if debug_mode else '关闭'}
  配置环境: {args.config}
========================================
    """)
    
    # 启动Flask应用
    app.run(
        host=args.host,
        port=args.port,
        debug=debug_mode,
        threaded=True
    )


if __name__ == '__main__':
    main()
