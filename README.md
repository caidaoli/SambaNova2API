# SambaNova OpenAI Proxy Service

A proxy service that provides SambaNova AI models through OpenAI-compatible API format. This service automatically handles SambaNova platform authentication and provides standard OpenAI API compatible endpoints.

## Features

- **OpenAI Compatible API**: Supports standard `/v1/chat/completions` and `/v1/models` endpoints
- **Automatic Token Management**: Automatically obtains and refreshes SambaNova access tokens with background refresh
- **Streaming & Non-streaming**: Supports real-time streaming and complete response modes
- **Connection Pool Optimization**: Uses HTTP/2 and connection reuse for better performance
- **Secure Authentication**: Supports local API key validation
- **Health Monitoring**: Provides service status and token status monitoring
- **Web Interface**: Friendly status monitoring web page

## Quick Start

### Environment Variables

Create a `.env` file and set the following environment variables:

```bash
# SambaNova account credentials (required)
SAMBA_EMAIL=your-email@example.com
SAMBA_PASSWORD=your-password

# Local API key (optional, for client authentication)
LOCAL_API_KEY=your-secret-api-key

# Token cache time (seconds, default 7 days)
TOKEN_CACHE_TIME=604800

# Other configurations (optional)
FINGERPRINT_PREFIX=anon_
SAMBA_COMPLETION_URL=https://cloud.sambanova.ai/api/completion
SAMBA_MODELS_URL=https://api.sambanova.ai/v1/models
```

### Docker Deployment

Run with Docker:

```bash
# Build image
docker build -t sambanova-proxy .

# Run container
docker run -d \
  --name sambanova-proxy \
  -p 6666:6666 \
  --env-file .env \
  sambanova-proxy
```

Or use docker-compose:

```bash
docker-compose up -d
```

### Local Development

1. Install dependencies:
```bash
pip install -r requirement.txt
```

2. Run the service:
```bash
python app.py
```

The service will start at `http://localhost:6666`.

## API Usage

### Get Available Models

```bash
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:6666/v1/models
```

### Chat Completions (Non-streaming)

```bash
curl -X POST http://localhost:6666/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-R1",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false,
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

### Chat Completions (Streaming)

```bash
curl -X POST http://localhost:6666/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "DeepSeek-R1",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

### Service Status

Visit `http://localhost:6666/info` for service status:

```json
{
  "status": "running",
  "api_key_configured": true,
  "samba_credentials_configured": true,
  "token_status": "active",
  "token_expires_in": 604800
}
```

Visit `http://localhost:6666/` for the friendly web status page.

## Supported Models

The service supports all available models on the SambaNova platform, including:

- DeepSeek-R1
- Meta-Llama series
- Other open-source models supported by SambaNova

Use the `/v1/models` endpoint to get the real-time list of available models.

## Technical Implementation

- **Framework**: FastAPI + Hypercorn ASGI server
- **HTTP Client**: httpx with HTTP/2 and connection reuse
- **Authentication**: Automated Auth0 OAuth flow
- **Token Management**: Automatic background refresh with caching and expiration detection
- **Containerization**: Multi-stage Docker build, non-root user execution
- **Async Design**: Fully asynchronous architecture for high concurrency

## Deployment

### Port Configuration
- Default port: 6666
- Health check endpoints: `/` and `/info`
- Debug endpoint: `/debug/token` (recommend disabling in production)

### Security Considerations
- Container runs as non-root user (uid:1001)
- Supports local API key authentication
- Environment variables manage sensitive information
- HTTP/2 encrypted transmission
- Connection timeout and limit protection

### Performance Optimization
- Connection pool reuse (up to 50 connections)
- HTTP/2 support
- Token caching mechanism
- Asynchronous processing architecture

## Troubleshooting

### Token Issues
- Verify SambaNova account credentials are correct
- Check `/debug/token` endpoint for token status
- Tokens are automatically refreshed when expired
- 401 errors will trigger automatic token refresh

### Connection Issues
- Confirm SambaNova service is accessible
- Check network connectivity and firewall settings
- Review container logs: `docker logs sambanova-proxy`

### Performance Issues
- Monitor memory and CPU usage
- Check if connection pool configuration is appropriate
- Adjust token refresh intervals

## Development Info

- **Python Version**: 3.13
- **Main Dependencies**: 
  - FastAPI 0.115.0+
  - httpx 0.28.0+ (with HTTP/2 support)
  - hypercorn 0.17.0+
  - pydantic 2.10.0+
- **Architecture**: Async ASGI application
- **Authentication**: Auth0 integration

## Changelog

### v1.0.0
- Initial release
- OpenAI compatible API support
- Automatic token management
- Docker containerized deployment
- Web status monitoring interface

## License

This project is for learning and research purposes only. Please comply with SambaNova platform's terms of service and conditions.