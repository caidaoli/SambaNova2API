FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

# 复制应用代码
COPY app.py .

# 暴露端口
EXPOSE 7860

# 启动应用
CMD ["python", "app.py"] 