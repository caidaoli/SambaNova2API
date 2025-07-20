# 多阶段构建：依赖阶段
FROM python:3.13-slim as dependencies

# 设置环境变量优化Python执行
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

# 生产阶段
FROM python:3.13-slim as production

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# 创建非root用户
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# 设置工作目录
WORKDIR /app

# 从依赖阶段复制已安装的包
COPY --from=dependencies /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# 复制应用代码并设置权限
COPY --chown=appuser:appgroup app.py .

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 7860

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:7860/info', timeout=5)" || exit 1

# 使用hypercorn启动应用以获得更好的性能
CMD ["python", "app.py"] 