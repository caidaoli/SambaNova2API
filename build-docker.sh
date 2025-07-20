#!/bin/bash

# 本地Docker镜像构建和测试脚本
# 用于在推送到GitHub之前本地测试GHCR镜像构建

set -e

# 配置变量
REGISTRY="ghcr.io"
REPOSITORY="caidaoli/sambanova2api"  # GitHub会自动将仓库名转换为小写
IMAGE_NAME="$REGISTRY/$REPOSITORY"
VERSION="local-test"

echo "🔨 开始构建Docker镜像..."

# 构建镜像
docker build \
    --target production \
    --platform linux/amd64 \
    -t "$IMAGE_NAME:$VERSION" \
    -t "$IMAGE_NAME:latest" \
    .

echo "✅ 镜像构建完成！"

# 显示镜像信息
echo "📊 镜像信息："
docker images | grep "$REPOSITORY" | head -5

echo ""
echo "🧪 测试镜像运行..."

# 创建测试用的环境变量文件
cat > .env.test << EOF
SAMBA_EMAIL=test@example.com
SAMBA_PASSWORD=test_password
LOCAL_API_KEY=test_api_key_$(openssl rand -hex 16)
EOF

# 运行容器进行测试
CONTAINER_ID=$(docker run -d \
    --name sambanova-test-$(date +%s) \
    --env-file .env.test \
    -p 8000:8000 \
    "$IMAGE_NAME:$VERSION")

echo "🚀 容器已启动，ID: $CONTAINER_ID"

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🔍 执行健康检查..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ 健康检查通过！"
else
    echo "❌ 健康检查失败，查看容器日志："
    docker logs $CONTAINER_ID
fi

# 显示容器状态
echo "📋 容器状态："
docker ps | grep sambanova-test

echo ""
echo "🎯 测试完成！"
echo "📍 访问地址: http://localhost:8000"
echo "📖 API文档: http://localhost:8000/docs"
echo ""
echo "🛑 停止测试容器："
echo "   docker stop $CONTAINER_ID"
echo "   docker rm $CONTAINER_ID"
echo ""
echo "🚀 推送到GHCR.io (需要先登录)："
echo "   docker login ghcr.io"
echo "   docker push $IMAGE_NAME:latest"

# 清理测试环境文件
rm -f .env.test

echo ""
echo "🔧 GitHub Actions将自动构建多架构镜像 (linux/amd64, linux/arm64)"
echo "📦 推送代码到GitHub后，镜像将自动发布到: $IMAGE_NAME"
