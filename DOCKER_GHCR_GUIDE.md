# GHCR.io 镜像部署指南

本项目已配置自动构建并推送Docker镜像到GitHub Container Registry (GHCR.io)。

## 🚀 自动化部署

### GitHub Actions工作流

项目已配置GitHub Actions工作流 (`.github/workflows/docker-build.yml`)，将在以下情况自动触发：

- 推送到 `main` 或 `master` 分支
- 创建新的 Git 标签 (如 `v1.0.0`)
- 手动触发工作流
- Pull Request

### 构建的镜像标签

- `ghcr.io/caidaoli/sambanovo2api:latest` - 最新主分支版本
- `ghcr.io/caidaoli/sambanovo2api:main` - 主分支版本
- `ghcr.io/caidaoli/sambanovo2api:v1.0.0` - 版本标签 (如果推送Git标签)

## 📦 使用已构建的镜像

### 直接运行

```bash
# 拉取并运行最新镜像
docker run -d \
  --name sambanova-api \
  -p 8000:8000 \
  -e SAMBA_EMAIL="your-email@example.com" \
  -e SAMBA_PASSWORD="your-password" \
  -e LOCAL_API_KEY="your-secret-key" \
  ghcr.io/caidaoli/sambanovo2api:latest
```

### 使用Docker Compose

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  sambanova-api:
    image: ghcr.io/caidaoli/sambanovo2api:latest
    container_name: sambanova-api
    ports:
      - "8000:8000"
    environment:
      - SAMBA_EMAIL=${SAMBA_EMAIL}
      - SAMBA_PASSWORD=${SAMBA_PASSWORD}
      - LOCAL_API_KEY=${LOCAL_API_KEY}
      - TOKEN_CACHE_TIME=604800
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

运行：
```bash
docker-compose up -d
```

### Kubernetes部署

创建 `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sambanova-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sambanova-api
  template:
    metadata:
      labels:
        app: sambanova-api
    spec:
      containers:
      - name: sambanova-api
        image: ghcr.io/caidaoli/sambanovo2api:latest
        ports:
        - containerPort: 8000
        env:
        - name: SAMBA_EMAIL
          valueFrom:
            secretKeyRef:
              name: sambanova-secrets
              key: email
        - name: SAMBA_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sambanova-secrets
              key: password
        - name: LOCAL_API_KEY
          valueFrom:
            secretKeyRef:
              name: sambanova-secrets
              key: api-key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: sambanova-api-service
spec:
  selector:
    app: sambanova-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## 🔧 本地开发和测试

### 本地构建测试

使用提供的脚本进行本地测试：

```bash
# 运行本地构建和测试
./build-docker.sh
```

### 手动构建

```bash
# 构建生产镜像
docker build --target production -t sambanova-api:local .

# 运行测试
docker run -d \
  --name sambanova-test \
  -p 8000:8000 \
  -e SAMBA_EMAIL="test@example.com" \
  -e SAMBA_PASSWORD="test_password" \
  sambanova-api:local
```

## 🏷️ 版本发布

### 创建新版本

1. 更新代码并提交到主分支
2. 创建并推送版本标签：

```bash
# 创建版本标签
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

3. GitHub Actions将自动构建并推送带版本标签的镜像

### 版本管理策略

- `latest` - 始终指向最新的稳定版本
- `main` - 主分支的最新构建
- `v1.0.0` - 特定版本标签
- `v1.0` - 主要版本和次要版本
- `v1` - 主要版本

## 🔒 安全配置

### 镜像权限

镜像默认配置为公开可访问。如需设置为私有：

1. 访问 GitHub 仓库 → Settings → Packages
2. 选择对应的包
3. 修改可见性设置

### 环境变量安全

生产环境中请使用以下方式管理敏感信息：

- Docker Secrets
- Kubernetes Secrets
- 环境变量管理工具 (如 HashiCorp Vault)

切勿在代码或Docker镜像中硬编码敏感信息。

## 📊 多架构支持

镜像支持以下架构：
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64/AArch64)

Docker会自动选择适合您系统架构的镜像版本。

## 🔍 故障排除

### 查看构建日志

访问 GitHub Actions 页面查看构建日志：
`https://github.com/caidaoli/SambaNova2API/actions`

### 常见问题

1. **镜像拉取失败**
   - 检查网络连接
   - 确认镜像名称和标签正确
   - 检查GHCR.io服务状态

2. **容器启动失败**
   - 检查环境变量设置
   - 查看容器日志：`docker logs <container_name>`
   - 确认端口未被占用

3. **健康检查失败**
   - 检查服务启动时间
   - 确认防火墙设置
   - 验证依赖服务可用性

## 📞 支持

如遇问题，请在GitHub仓库创建Issue：
`https://github.com/caidaoli/SambaNova2API/issues`
