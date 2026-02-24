# 依赖问题解决方案

## 📋 问题现象

今天运行程序时遇到：
```
No module named uvicorn
```

随后尝试重装依赖时遇到：
```
ERROR: No matching distribution found for mediapipe>=0.10.9
```

## 🔍 根本原因分析

### 1. **虚拟环境依赖丢失**
- 虚拟环境中的包被清理或损坏
- 可能由于系统清理工具、磁盘空间清理等操作导致

### 2. **Python 版本不兼容（主要问题）**
- 当前系统 Python 版本：**3.13.3**
- MediaPipe 支持的最高版本：**Python 3.12**
- MediaPipe 官方尚未发布支持 Python 3.13 的版本

### 3. **SSL 证书问题（次要问题）**
- macOS 系统的 OpenSSL 证书文件丢失
- 路径 `/usr/local/etc/openssl@3/cert.pem` 不存在
- 可能由于 Homebrew 更新或系统更新导致

## ❓ 为什么前两天能运行，今天就不行了？

### 可能的原因：

1. **虚拟环境重建**
   - 之前的虚拟环境使用的是 Python 3.11 或 3.12
   - 虚拟环境被删除或损坏后，重建时使用了系统默认的 Python 3.13
   
2. **Python 版本更新**
   - 最近通过 Homebrew 更新了 Python 到 3.13
   - 系统默认 Python 从 3.12 变成了 3.13

3. **系统/依赖清理**
   - 磁盘清理工具清理了虚拟环境
   - Homebrew 清理命令删除了旧版本依赖

## ✅ 解决方案

### 方案 1：使用 Python 3.12 重建虚拟环境（推荐）

#### 步骤 1：安装 Python 3.12
```bash
# 使用 Homebrew 安装
brew install python@3.12
```

#### 步骤 2：删除现有虚拟环境
```bash
cd /Users/liuyu/Code/shotImprovement
rm -rf venv
```

#### 步骤 3：使用 Python 3.12 创建新虚拟环境
```bash
python3.12 -m venv venv
source venv/bin/activate
```

#### 步骤 4：升级 pip 并安装依赖
```bash
pip install --upgrade pip
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
```

#### 步骤 5：启动服务器
```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 方案 2：修复 SSL 证书问题（可选）

如果不想使用 `--trusted-host` 参数，可以修复 SSL 证书：

#### 方法 A：使用 certifi 包
```bash
pip install --upgrade certifi
python3 -m certifi
```

#### 方法 B：链接系统证书
```bash
brew install openssl@3
ln -s $(brew --prefix)/etc/openssl@3/cert.pem /usr/local/etc/openssl@3/cert.pem
```

## 📦 依赖版本兼容性

| 包名 | 原版本 | 修改后 | Python 3.13 支持 |
|------|--------|--------|------------------|
| fastapi | 0.109.0 | >=0.109.0 | ✅ |
| uvicorn | 0.27.0 | >=0.27.0 | ✅ |
| opencv-python-headless | 4.9.0.80 | >=4.9.0.80 | ✅ |
| **mediapipe** | **0.10.9** | **>=0.10.9** | **❌** |
| numpy | 1.24.3 | >=1.26.0 | ✅ |

## 🎯 最佳实践建议

### 1. **固定 Python 版本**
在虚拟环境中指定使用的 Python 版本：
```bash
# 创建时指定版本
python3.12 -m venv venv
```

### 2. **记录环境信息**
创建 `.python-version` 文件：
```bash
echo "3.12" > .python-version
```

### 3. **使用 pyenv 管理 Python 版本**
```bash
# 安装 pyenv
brew install pyenv

# 安装并使用 Python 3.12
pyenv install 3.12.7
pyenv local 3.12.7
```

### 4. **定期备份虚拟环境**
```bash
# 导出当前安装的包
pip freeze > requirements-freeze.txt
```

### 5. **配置 pip 镜像源**
创建 `~/.pip/pip.conf`:
```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
```

## 🔄 当前状态

- [x] 问题诊断完成
- [x] 识别根本原因（Python 3.13 不兼容）
- [ ] Python 3.12 安装中（Homebrew 编译需要 10-15 分钟）
- [ ] 重建虚拟环境
- [ ] 重装依赖
- [ ] 启动服务器测试

## 📝 后续优化

1. **考虑使用 Docker**
   - 避免环境依赖问题
   - 确保开发和生产环境一致

2. **添加环境检查脚本**
   - 在启动前检查 Python 版本
   - 自动验证依赖完整性

3. **监控 MediaPipe 更新**
   - 等待官方发布 Python 3.13 支持版本
   - 届时可以升级到 Python 3.13

## 📚 相关链接

- [MediaPipe Python Compatibility](https://github.com/google/mediapipe/releases)
- [Python Release Cycle](https://devguide.python.org/versions/)
- [Homebrew Python Formulae](https://formulae.brew.sh/formula/python@3.12)

---

**问题解决时间估计**：10-20 分钟（取决于 Python 3.12 编译速度）
