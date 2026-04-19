#!/bin/bash

# 应用基础配置
APP_DIR="/mnt/large_storage/AGitHub/dowload/download_site"
APP_NAME="download-site"
PYTHON_CMD="python"
PORT=5000

# 切换到应用目录
cd "$APP_DIR"

# 清理旧进程
echo "🧹 清理旧进程..."
fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 2

# 停止并移除旧容器
echo "🛑 停止旧容器..."
docker stop $APP_NAME 2>/dev/null || true
docker rm $APP_NAME 2>/dev/null || true
sleep 2

# 清理旧镜像
echo "🗑️ 清理旧镜像..."
docker rmi $APP_NAME:latest 2>/dev/null || true
sleep 2

# 构建新镜像
echo "🏗️ 构建Docker镜像..."
docker build -t $APP_NAME .

# 启动新容器
echo "🚀 启动服务..."
docker run -d --name $APP_NAME -p ${PORT}:${PORT} -v ${APP_DIR}/uploads:/app/uploads -v ${APP_DIR}/instance:/app/instance $APP_NAME

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 测试访问
echo "🔍 测试访问..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/)

if [ "$RESPONSE" = "200" ]; then
    echo "✅ 服务启动成功!"
    echo "🌐 访问地址: http://localhost:${PORT}"
    echo "🛠️  管理后台: http://localhost:${PORT}/admin"
else
    echo "❌ 服务启动失败，HTTP状态码: $RESPONSE"
    echo "📋 日志:"
    docker logs $APP_NAME
fi