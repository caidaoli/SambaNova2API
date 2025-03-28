"""
SambaNova OpenAI 接口代理 (支持模型列表透传和自动登录)
"""

import os
import uuid
import json
import time
import asyncio
import httpx
import secrets
import urllib.parse
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fake_useragent import UserAgent
# 修复 Pydantic 导入
try:
    # 尝试从 pydantic-settings 导入 (Pydantic v2)
    from pydantic_settings import BaseSettings
except ImportError:
    # 回退到旧版本 (Pydantic v1)
    from pydantic import BaseSettings

# ================ 配置 ================
class Settings(BaseSettings):
    # SambaNova 配置
    SAMBA_EMAIL: str = os.getenv("SAMBA_EMAIL", "")
    SAMBA_PASSWORD: str = os.getenv("SAMBA_PASSWORD", "")
    SAMBA_COMPLETION_URL: str = os.getenv("SAMBA_COMPLETION_URL", "https://cloud.sambanova.ai/api/completion")
    SAMBA_MODELS_URL: str = os.getenv("SAMBA_MODELS_URL", "https://api.sambanova.ai/v1/models")
    
    # 本地API密钥配置
    LOCAL_API_KEY: str = os.getenv("LOCAL_API_KEY", secrets.token_urlsafe(32))
    
    # 其他配置
    TOKEN_CACHE_TIME: int = int(os.getenv("TOKEN_CACHE_TIME", 604800))  # 默认缓存7天 (7*24*60*60=604800秒)
    FINGERPRINT_PREFIX: str = os.getenv("FINGERPRINT_PREFIX", "anon_")
    
    class Config:
        env_file = ".env"

settings = Settings()
# =====================================

app = FastAPI(title="SambaNova OpenAI Proxy with Auto-Login")
security = HTTPBearer()

# 全局变量存储访问令牌和过期时间
access_token = None
token_expiry = 0
token_lock = asyncio.Lock()

def generate_fingerprint() -> str:
    """生成符合格式要求的随机指纹"""
    return f"{settings.FINGERPRINT_PREFIX}{uuid.uuid4().hex[:20]}"

async def validate_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """验证本地API密钥并返回SambaNova访问令牌"""
    api_key = credentials.credentials
    
    # 如果未配置本地API密钥或为空，则跳过验证
    if settings.LOCAL_API_KEY and settings.LOCAL_API_KEY.strip():
        # 验证本地API密钥
        if api_key != settings.LOCAL_API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        print("[警告] LOCAL_API_KEY未配置或为空，跳过API密钥验证")
    
    # 获取或刷新SambaNova访问令牌
    token = await get_samba_token()
    if not token:
        raise HTTPException(
            status_code=500,
            detail="Failed to obtain SambaNova access token. Check server logs for details."
        )
    
    return token

async def get_samba_token() -> Optional[str]:
    """获取或刷新SambaNova访问令牌"""
    global access_token, token_expiry
    
    # 使用锁防止并发请求同时刷新令牌
    async with token_lock:
        current_time = time.time()
        
        # 如果令牌有效，直接返回
        if access_token and current_time < token_expiry:
            print(f"[令牌] 使用缓存令牌: {access_token}")
            return access_token
        
        # 否则获取新令牌
        try:
            # 检查凭据是否已配置
            if not settings.SAMBA_EMAIL or not settings.SAMBA_PASSWORD:
                print("[错误] 未配置SambaNova凭据，请设置SAMBA_EMAIL和SAMBA_PASSWORD环境变量")
                return None
                
            print(f"[令牌] 开始获取新令牌... 邮箱: {settings.SAMBA_EMAIL}")
            auth = SambaAuthAsync(settings.SAMBA_EMAIL, settings.SAMBA_PASSWORD)
            new_token = await auth.login()
            
            if new_token:
                access_token = new_token
                token_expiry = current_time + settings.TOKEN_CACHE_TIME
                print(f"[令牌更新成功] 完整令牌: {new_token}")
                print(f"[令牌更新成功] 令牌将在 {settings.TOKEN_CACHE_TIME} 秒后过期")
                return access_token
            else:
                print("[令牌获取失败] 请检查SambaNova凭据是否正确")
                return None
        except Exception as e:
            print(f"[令牌获取异常] {str(e)}")
            return None

def reset_token_expiry():
    """重置令牌过期时间，强制下次请求重新获取令牌"""
    global token_expiry
    token_expiry = 0
    print("[令牌] 令牌已过期，将在下次请求时重新获取")

async def forward_get_request(url: str, token: str) -> httpx.Response:
    """转发 GET 请求到目标接口"""
    headers = {
        "accept": "application/json",
        "user-agent": "SambaNova-Proxy/1.0",
        "origin": "https://cloud.sambanova.ai",
        "referer": "https://cloud.sambanova.ai/"
    }
    
    cookies = {
        "access_token": token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=10.0
            )
            
            # 检查是否需要刷新令牌
            if resp.status_code == 401:
                # 令牌已过期，需要刷新
                reset_token_expiry()
                raise HTTPException(401, "Token expired, please retry")
                
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # 令牌已过期，需要刷新
                reset_token_expiry()
                raise HTTPException(401, "Token expired, please retry")
            raise HTTPException(e.response.status_code, f"Upstream error: {e.response.text}")

async def forward_post_request(url: str, payload: dict, token: str) -> httpx.Response:
    """转发 POST 请求到目标接口"""
    headers = {
        "content-type": "application/json",
        "user-agent": "SambaNova-Proxy/1.0",
        "origin": "https://cloud.sambanova.ai",
        "referer": "https://cloud.sambanova.ai/"
    }
    
    cookies = {
        "access_token": token
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                json=payload,
                headers=headers,
                cookies=cookies,
                timeout=30.0
            )
            
            # 检查是否需要刷新令牌
            if resp.status_code == 401:
                # 令牌已过期，需要刷新
                reset_token_expiry()
                raise HTTPException(401, "Token expired, please retry")
                
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # 令牌已过期，需要刷新
                reset_token_expiry()
                raise HTTPException(401, "Token expired, please retry")
            raise HTTPException(e.response.status_code, f"Upstream error: {e.response.text}")

@app.get("/v1/models")
async def list_models(token: str = Depends(validate_api_key)):
    """透传模型列表接口"""
    try:
        resp = await forward_get_request(settings.SAMBA_MODELS_URL, token)
        content = resp.json()
        json_str = json.dumps(content, separators=(',', ':'), ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')
        return JSONResponse(
            content=content,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(json_bytes)),
                "Cache-Control": "public, max-age=300"
            }
        )
    except httpx.RequestError as e:
        raise HTTPException(504, f"Gateway timeout: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Internal server error: {str(e)}")

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    token: str = Depends(validate_api_key)
):
    """处理对话请求"""
    try:
        openai_payload = await request.json()
        print(f"[请求] 收到聊天请求，模型: {openai_payload.get('model', 'DeepSeek-R1')}")
        
        samba_payload = {
            "body": {
                "model": openai_payload.get("model", "DeepSeek-R1"),
                "messages": openai_payload["messages"],
                "stream": True,
                "stop": openai_payload.get("stop", ["<|eot_id|>"]),
                "temperature": openai_payload.get("temperature", 0),
                "max_tokens": openai_payload.get("max_tokens", 2048),
                "do_sample": openai_payload.get("temperature", 0) > 0
            },
            "env_type": "text",
            "fingerprint": generate_fingerprint()
        }
        
        print(f"[转发] 使用令牌 {token[:10]}... 转发请求到 SambaNova")
        resp = await forward_post_request(settings.SAMBA_COMPLETION_URL, samba_payload, token)
        print(f"[响应] 成功获取响应，开始流式传输")
        
        return StreamingResponse(
            resp.aiter_bytes(),
            media_type="text/event-stream",
            headers={
                "X-Proxy-Version": "1.0",
                "X-Request-ID": str(uuid.uuid4())
            }
        )
    except HTTPException as e:
        print(f"[错误] HTTP异常: {e.detail}")
        raise
    except httpx.RequestError as e:
        print(f"[错误] 请求错误: {str(e)}")
        raise HTTPException(504, f"Gateway timeout: {str(e)}")
    except Exception as e:
        print(f"[错误] 未处理异常: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")

@app.get("/info")
async def get_info():
    """获取服务信息"""
    return {
        "status": "running",
        "api_key_configured": bool(settings.LOCAL_API_KEY),
        "samba_credentials_configured": bool(settings.SAMBA_EMAIL and settings.SAMBA_PASSWORD),
        "token_status": "active" if access_token and time.time() < token_expiry else "not_available",
        "token_expires_in": max(0, int(token_expiry - time.time())) if access_token else 0
    }

@app.get("/debug/token", include_in_schema=False)
async def debug_token():
    """调试端点：检查当前令牌状态"""
    global access_token, token_expiry
    current_time = time.time()
    
    return {
        "token_exists": access_token is not None,
        "token_prefix": access_token[:10] + "..." if access_token else None,
        "token_valid": access_token is not None and current_time < token_expiry,
        "expires_in_seconds": max(0, int(token_expiry - current_time)) if access_token else 0,
        "current_time": current_time,
        "expiry_time": token_expiry,
    }

@app.get("/", response_class=HTMLResponse)
async def root():
    """根路由健康检查，返回HTML界面"""
    current_time = time.time()
    token_valid = access_token is not None and current_time < token_expiry
    expires_in = max(0, int(token_expiry - current_time)) if access_token else 0
    
    # 计算过期时间的可读格式
    if expires_in > 0:
        days = expires_in // 86400
        hours = (expires_in % 86400) // 3600
        minutes = (expires_in % 3600) // 60
        expiry_readable = f"{days}天 {hours}小时 {minutes}分钟"
    else:
        expiry_readable = "已过期"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SambaNova OpenAI 代理服务</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 1px solid #eee;
                padding-bottom: 10px;
            }}
            .status-card {{
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .status-item {{
                margin-bottom: 10px;
                display: flex;
                justify-content: space-between;
            }}
            .status-label {{
                font-weight: bold;
                color: #555;
            }}
            .status-value {{
                text-align: right;
            }}
            .status-healthy {{
                color: #28a745;
                font-weight: bold;
            }}
            .status-warning {{
                color: #ffc107;
                font-weight: bold;
            }}
            .status-error {{
                color: #dc3545;
                font-weight: bold;
            }}
            .code-block {{
                background-color: #f1f1f1;
                padding: 15px;
                border-radius: 5px;
                font-family: monospace;
                overflow-x: auto;
            }}
            .footer {{
                margin-top: 30px;
                font-size: 0.9em;
                color: #6c757d;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <h1>SambaNova OpenAI 代理服务</h1>
        
        <div class="status-card">
            <h2>服务状态</h2>
            <div class="status-item">
                <span class="status-label">状态:</span>
                <span class="status-value status-healthy">运行中</span>
            </div>
            <div class="status-item">
                <span class="status-label">版本:</span>
                <span class="status-value">1.0.0</span>
            </div>
            <div class="status-item">
                <span class="status-label">令牌状态:</span>
                <span class="status-value {('status-healthy' if token_valid else 'status-error')}">
                    {('有效' if token_valid else '无效')}
                </span>
            </div>
            <div class="status-item">
                <span class="status-label">令牌过期时间:</span>
                <span class="status-value">{expiry_readable}</span>
            </div>
            <div class="status-item">
                <span class="status-label">SambaNova 凭据:</span>
                <span class="status-value {('status-healthy' if settings.SAMBA_EMAIL and settings.SAMBA_PASSWORD else 'status-error')}">
                    {('已配置' if settings.SAMBA_EMAIL and settings.SAMBA_PASSWORD else '未配置')}
                </span>
            </div>
            <div class="status-item">
                <span class="status-label">本地API密钥:</span>
                <span class="status-value {('status-healthy' if settings.LOCAL_API_KEY else 'status-warning')}">
                    {('已配置' if settings.LOCAL_API_KEY else '未配置')}
                </span>
            </div>
        </div>
                
        <div class="footer">
            <p>当前时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

class SambaAuthAsync:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.client = httpx.AsyncClient()
        self.ua = UserAgent()
        self.base_headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": "https://cloud.sambanova.ai",
            "referer": "https://cloud.sambanova.ai/",
            "user-agent": self.ua.random
        }
        self.config = None
        self.nonce = None  # 确保nonce属性存在

    async def _get_config(self):
        """获取动态配置信息"""
        config_url = "https://cloud.sambanova.ai/api/config"
        response = await self.client.get(config_url, headers=self.base_headers)
        response.raise_for_status()
        self.config = response.json()
        print(f"[配置获取成功] ClientID: {self.config['clientId']}")

    async def _get_login_ticket(self):
        """获取登录票据"""
        auth_url = f"https://{self.config['issuerBaseUrl']}/co/authenticate"
        payload = {
            "client_id": self.config["clientId"],
            "username": self.email,
            "password": self.password,
            "realm": "Username-Password-Authentication",
            "credential_type": "http://auth0.com/oauth/grant-type/password-realm"
        }
        
        headers = {**self.base_headers, "content-type": "application/json"}

        response = await self.client.post(auth_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["login_ticket"]

    async def _get_auth_code(self, login_ticket: str):
        """获取授权码"""
        state = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(32)  # 保存nonce到实例变量
        
        params = {
            "client_id": self.config["clientId"],
            "response_type": "code",
            "redirect_uri": self.config["redirectURL"],
            "scope": "openid profile email",
            "nonce": self.nonce,
            "state": state,
            "login_ticket": login_ticket,
            "realm": "Username-Password-Authentication",
            "auth0Client": "eyJuYW1lIjoibG9jay5qcyIsInZlcnNpb24iOiIxMi4zLjAiLCJlbnYiOnsiYXV0aDAuanMiOiI5LjIyLjEiLCJhdXRoMC5qcy11bHAiOiI5LjIyLjEifX0="
        }

        auth_url = f"https://{self.config['issuerBaseUrl']}/authorize"
        response = await self.client.get(
            auth_url,
            params=params,
            follow_redirects=False
        )
        
        if response.status_code == 302:
            location = response.headers["location"]
            parsed = urllib.parse.urlparse(location)
            query = urllib.parse.parse_qs(parsed.query)
            return query.get("code", [None])[0], state
        raise Exception(f"未收到302重定向，实际状态码：{response.status_code}")

    async def _exchange_token(self, code: str, state: str):
        """交换访问令牌"""
        # 设置必要的cookies
        self.client.cookies.set("nonce", self.nonce, domain="cloud.sambanova.ai")
        
        callback_url = f"{self.config['redirectURL']}?code={code}&state={state}"
        response = await self.client.get(
            callback_url,
            headers={
                **self.base_headers,
                "sec-fetch-site": "same-site",
                "sec-fetch-mode": "navigate",
                "sec-fetch-user": "?1",
                "sec-fetch-dest": "document"
            },
            follow_redirects=True
        )
        
        # 从cookies中提取access_token
        for cookie in self.client.cookies.jar:
            if cookie.name == "access_token" and "sambanova.ai" in cookie.domain:
                return cookie.value
        raise Exception("未找到access_token")

    async def login(self):
        """完整登录流程"""
        try:
            await self._get_config()
            login_ticket = await self._get_login_ticket()
            print(f"[登录票据获取成功] 完整票据: {login_ticket}")
            
            auth_code, state = await self._get_auth_code(login_ticket)
            if not auth_code:
                raise Exception("授权码获取失败")
            print(f"[授权码获取成功] 完整授权码: {auth_code}")
            print(f"[授权状态] state: {state}")
            
            token = await self._exchange_token(auth_code, state)
            print(f"[令牌获取成功] 完整令牌: {token}")
            return token
            
        except Exception as e:
            print(f"[登录失败] 详细错误: {str(e)}")
            return None
        finally:
            await self.client.aclose()

@app.on_event("startup")
async def startup_event():
    """应用启动时预获取令牌"""
    print("\n" + "="*50)
    print("[启动] SambaNova OpenAI 代理服务启动")
    print("="*50)
    
    # 检查环境变量
    print(f"[环境] SAMBA_EMAIL: {'已设置' if settings.SAMBA_EMAIL else '未设置'}")
    print(f"[环境] SAMBA_PASSWORD: {'已设置' if settings.SAMBA_PASSWORD else '未设置'}")
    print(f"[环境] LOCAL_API_KEY: {'已设置' if settings.LOCAL_API_KEY else '未设置'}")
    
    # 尝试直接登录
    print("[登录] 开始尝试登录...")
    try:
        auth = SambaAuthAsync(settings.SAMBA_EMAIL, settings.SAMBA_PASSWORD)
        token = await auth.login()
        
        if token:
            global access_token, token_expiry
            access_token = token
            token_expiry = time.time() + settings.TOKEN_CACHE_TIME
            print(f"[登录] 登录成功! 令牌: {token}")
            print(f"[登录] 令牌将在 {settings.TOKEN_CACHE_TIME} 秒后过期")
        else:
            print("[登录] 登录失败，未获取到令牌")
    except Exception as e:
        print(f"[登录] 登录过程发生异常: {str(e)}")
    
    print("="*50 + "\n")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860) 