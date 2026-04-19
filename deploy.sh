#!/bin/bash

# 文件分享下载站点 Docker 部署脚本

set -e

echo "🚀 开始部署文件分享下载站点..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 docker-compose 是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ docker-compose 未安装，请先安装 docker-compose"
    exit 1
fi

# 复制环境变量文件
if [ ! -f .env ]; then
    echo "📋 复制环境变量配置文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件设置 SECRET_KEY"
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p uploads instance

# 构建和启动服务
echo "🏗️  构建 Docker 镜像..."
if command -v docker-compose &> /dev/null; then
    docker-compose build
    echo "🚀 启动服务..."
    docker-compose up -d
else
    docker compose build
    echo "🚀 启动服务..."
    docker compose up -d
fi

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo ""
echo "✅ 部署完成!"
echo ""
echo "📱 访问地址:"
echo "   网站首页: http://localhost:5000"
echo "   管理后台: http://localhost:5000/admin"
echo ""
echo "🛠️  管理命令:"
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose down"
echo "   重启服务: docker-compose restart"
echo ""
echo "⚠️  重要提醒:"
echo "   请务必修改 .env 文件中的 SECRET_KEY"