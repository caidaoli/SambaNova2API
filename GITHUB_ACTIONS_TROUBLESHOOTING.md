# GitHub Actions Attestation 故障排除指南

## 问题描述

如果您在GitHub Actions中遇到以下错误：
```
Error: Failed to persist attestation: Resource not accessible by integration
```

这通常是由于权限配置或仓库设置问题导致的。

## 解决方案

### 方案1: 权限修复 (已应用)

我们已经在 `docker-build.yml` 中添加了必要的权限：

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
  attestations: write  # 新增的权限
```

并添加了条件检查，只在非Pull Request时运行attestation：

```yaml
- name: Generate artifact attestation
  if: ${{ github.event_name != 'pull_request' }}
  uses: actions/attest-build-provenance@v1
  # ...
```

### 方案2: 使用简化工作流

如果方案1仍然失败，可以使用 `docker-build-simple.yml` 工作流：

1. **禁用原工作流**：
   ```bash
   # 重命名原文件以禁用
   mv .github/workflows/docker-build.yml .github/workflows/docker-build.yml.backup
   ```

2. **激活简化工作流**：
   ```bash
   # 重命名简化工作流为主工作流
   mv .github/workflows/docker-build-simple.yml .github/workflows/docker-build.yml
   ```

### 方案3: 手动移除Attestation步骤

如果您想保持当前工作流但移除attestation，可以删除以下步骤：

```yaml
# 删除这整个步骤
- name: Generate artifact attestation
  if: ${{ github.event_name != 'pull_request' }}
  uses: actions/attest-build-provenance@v1
  with:
    subject-name: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
    subject-digest: ${{ steps.build.outputs.digest }}
    push-to-registry: true
```

## Attestation的作用

GitHub Attestation 提供：
- **Supply Chain Security**: 验证构建来源
- **Provenance Tracking**: 跟踪构建过程
- **Signature Verification**: 数字签名验证

**注意**: 移除attestation不会影响Docker镜像的构建和推送，只是失去了额外的安全验证功能。

## 检查构建状态

访问以下链接查看构建状态：
- Actions页面: https://github.com/caidaoli/SambaNova2API/actions
- Package页面: https://github.com/caidaoli/SambaNova2API/pkgs/container/sambanovo2api

## 替代解决方案

如果attestation持续失败，可以考虑：

1. **手动签名**: 使用cosign等工具手动签名镜像
2. **第三方CI/CD**: 使用其他CI/CD平台
3. **本地构建**: 使用本地构建脚本 `build-docker.sh`

## 立即可用的简化命令

如果需要立即禁用attestation并使用简化工作流：

```bash
cd /path/to/your/repo
git mv .github/workflows/docker-build.yml .github/workflows/docker-build-with-attestation.yml.backup
git mv .github/workflows/docker-build-simple.yml .github/workflows/docker-build.yml
git commit -m "switch to simple docker build workflow without attestation"
git push origin main
```

这将立即切换到无attestation的稳定工作流。
