# Dolphin API 使用说明

## 📖 概述

这是基于Dolphin模型的文档图像解析API服务，提供页面级和元素级的文档解析功能。

## 🚀 快速开始

### 1. 安装依赖

```bash
# 激活conda环境
conda activate dolphin

# 安装依赖包
pip install -r requirements.txt
```

### 2. 下载模型

确保已下载Dolphin模型文件并放置在以下位置之一：
- `./checkpoints/` - 原始模型格式
- `./hf_model/` - Hugging Face模型格式

### 3. 配置API Keys（推荐）

#### 快速配置（推荐）

使用提供的配置脚本：

```bash
# 运行交互式配置脚本
./setup_env.sh
```

#### 手动配置

创建`.env.local`文件来配置API Keys：

```bash
# 方式1: 使用生成脚本
python generate_api_key.py --count 3 --env --output .env.local

# 方式2: 复制示例文件
cp env_example.txt .env.local

# 编辑.env.local文件，设置您的API Keys
# API_KEYS=your_api_key_1,your_api_key_2,your_api_key_3
```

### 4. 启动服务

```bash
# 使用启动脚本（自动读取.env.local）
./start_api_server.sh

# 或直接运行（自动读取.env.local）
python api_server.py --config ./config/Dolphin.yaml --host 0.0.0.0 --port 8765

# 不使用.env.local文件
python api_server.py --config ./config/Dolphin.yaml --host 0.0.0.0 --port 8765 --no-env

# 命令行指定API Keys（会与.env.local合并）
python api_server.py --config ./config/Dolphin.yaml --host 0.0.0.0 --port 8765 \
    --api-keys "additional_key_1" "additional_key_2"

# 从文件读取API Keys（会与.env.local合并）
python api_server.py --config ./config/Dolphin.yaml --host 0.0.0.0 --port 8765 \
    --api-keys-file api_keys.txt
```

### 5. 访问API

- **本地访问**: http://localhost:8765
- **公网访问**: http://162.105.160.152:8765  
- **Tailscale访问**: http://100.71.111.116:8765
- **API文档**: http://localhost:8765/docs

## 🔧 API接口

### 🔐 认证方式

如果服务器启用了API Key认证，需要在请求中包含认证信息：

**方式1: Bearer Token（推荐）**
```
Authorization: Bearer your_api_key
```

**方式2: 自定义Header**
```
X-API-Key: your_api_key
```

### 健康检查

```bash
GET /health
```

检查服务状态和模型加载情况。**此接口不需要认证**。

### 页面级解析

#### 1. 使用Base64编码（POST /parse_page）

```python
import requests
import base64

# 将图像转为base64
with open("document.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# 发送请求（不需要认证）
response = requests.post("http://localhost:8765/parse_page", json={
    "image_base64": image_base64,
    "max_batch_size": 4
})

# 发送请求（需要认证）
headers = {"Authorization": "Bearer your_api_key"}
response = requests.post("http://localhost:8765/parse_page", json={
    "image_base64": image_base64,
    "max_batch_size": 4
}, headers=headers)

result = response.json()
```

#### 2. 使用文件上传（POST /upload_parse_page）

```python
import requests

# 上传文件（不需要认证）
with open("document.jpg", "rb") as f:
    files = {"file": f}
    data = {"max_batch_size": 4}
    
    response = requests.post("http://localhost:8765/upload_parse_page", 
                           files=files, data=data)

# 上传文件（需要认证）
with open("document.jpg", "rb") as f:
    files = {"file": f}
    data = {"max_batch_size": 4}
    headers = {"Authorization": "Bearer your_api_key"}
    
    response = requests.post("http://localhost:8765/upload_parse_page", 
                           files=files, data=data, headers=headers)

result = response.json()
```

### 元素级解析

#### 1. 使用Base64编码（POST /parse_element）

```python
import requests
import base64

# 将图像转为base64
with open("table.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# 发送请求
response = requests.post("http://localhost:8765/parse_element", json={
    "image_base64": image_base64,
    "element_type": "table"  # text, table, formula
})

result = response.json()
```

#### 2. 使用文件上传（POST /upload_parse_element）

```python
import requests

# 上传文件
with open("table.jpg", "rb") as f:
    files = {"file": f}
    data = {"element_type": "table"}
    
    response = requests.post("http://localhost:8765/upload_parse_element", 
                           files=files, data=data)

result = response.json()
```

## 📊 响应格式

所有API接口返回统一的JSON格式：

```json
{
    "success": true,
    "message": "解析成功",
    "results": [
        {
            "label": "text",
            "bbox": [x1, y1, x2, y2],
            "text": "识别的文本内容",
            "reading_order": 0
        }
    ],
    "processing_time": 2.45
}
```

## 🧪 测试客户端

使用提供的测试客户端进行测试：

```bash
# 健康检查
python api_client_test.py --test-type health

# 页面级解析（使用base64方式）
python api_client_test.py --test-type page --image ./demo/page_imgs/page_1.jpeg

# 页面级解析（使用文件上传方式）
python api_client_test.py --test-type page --image ./demo/page_imgs/page_1.jpeg --upload

# 元素级解析（表格）
python api_client_test.py --test-type element --image ./demo/element_imgs/table_1.jpeg --element-type table --upload

# 远程服务器测试
python api_client_test.py --url http://162.105.160.152:8765 --test-type health

# 使用API Key认证（命令行指定）
python api_client_test.py --test-type page --image ./demo/page_imgs/page_1.jpeg --api-key "your_api_key"

# 使用.env.local文件中的API Key（自动读取）
python api_client_test.py --test-type page --image ./demo/page_imgs/page_1.jpeg

# 不使用.env.local文件
python api_client_test.py --test-type page --image ./demo/page_imgs/page_1.jpeg --no-env

# 远程服务器 + API Key认证
python api_client_test.py --url http://162.105.160.152:8765 --test-type page \
    --image ./demo/page_imgs/page_1.jpeg --api-key "your_api_key"
```

## 🎯 支持的元素类型

- **text**: 文本段落
- **table**: 表格
- **formula**: 数学公式

## 📝 参数说明

### 页面级解析参数

- `image_base64`: Base64编码的图像数据
- `max_batch_size`: 并行处理的最大批次大小（默认4）

### 元素级解析参数

- `image_base64`: Base64编码的图像数据
- `element_type`: 元素类型（text, table, formula）

## 🔍 错误处理

API会返回详细的错误信息：

```json
{
    "success": false,
    "message": "具体错误描述",
    "processing_time": 0.05
}
```

常见错误：
- `400`: 请求参数错误（图像格式不支持、元素类型错误等）
- `401`: 认证失败（API Key无效或缺失）
- `500`: 服务器内部错误（模型推理失败等）
- `503`: 服务不可用（模型未加载）

## 🚦 性能建议

1. **批次大小**: 根据GPU内存调整`max_batch_size`，过大可能导致OOM
2. **图像尺寸**: 建议图像不要过大，会影响处理速度
3. **并发请求**: 单个模型实例建议避免过多并发请求
4. **缓存**: 对于重复的图像可以考虑结果缓存

## 🔑 API Key管理

### 方式1: .env.local文件（推荐）

创建`.env.local`文件来配置API Keys：

```bash
# 复制示例文件
cp env_example.txt .env.local

# 编辑.env.local文件
nano .env.local
```

`.env.local`文件内容示例：

```bash
# 逗号分隔多个API Key
API_KEYS=abc123def456ghi789jkl012mno345pqr678,def456ghi789jkl012mno345pqr678stu901

# 或空格分隔
# API_KEYS=abc123def456ghi789jkl012mno345pqr678 def456ghi789jkl012mno345pqr678stu901

# 单个API Key
# API_KEYS=your_single_api_key_here
```

### 方式2: 命令行参数

```bash
# 命令行指定
python api_server.py --api-keys "key1" "key2" "key3"

# 禁用.env.local文件
python api_server.py --api-keys "key1" "key2" --no-env
```

### 方式3: 文件加载

创建`api_keys.txt`文件，每行一个API Key：

```
abc123def456ghi789jkl012mno345pqr678
def456ghi789jkl012mno345pqr678stu901
ghi789jkl012mno345pqr678stu901vwx234
```

```bash
# 从文件加载
python api_server.py --api-keys-file api_keys.txt
```

### 混合使用

多种方式可以同时使用，API Keys会合并：

```bash
# .env.local + 命令行 + 文件
python api_server.py --api-keys "emergency_key" --api-keys-file api_keys.txt
```

### 生成API Key

#### 方式1: 使用提供的生成脚本（推荐）

```bash
# 生成单个API Key
python generate_api_key.py

# 生成多个API Key
python generate_api_key.py --count 3

# 生成并直接输出.env.local格式
python generate_api_key.py --count 3 --env

# 生成并保存到.env.local文件
python generate_api_key.py --count 3 --env --output .env.local

# 生成不同类型的API Key
python generate_api_key.py --type uuid
python generate_api_key.py --type urlsafe
python generate_api_key.py --type hex --length 16
```

#### 方式2: 手动生成

```bash
# 使用openssl生成随机API Key
openssl rand -hex 32

# 使用Python生成
python -c "import secrets; print(secrets.token_hex(32))"

# 使用uuid
python -c "import uuid; print(uuid.uuid4().hex)"
```

## 🔒 安全注意事项

1. **API Key管理**: 定期更换API Key，不要在代码中硬编码
2. **CORS限制**: 生产环境应限制CORS域名
3. **请求频率**: 添加请求频率限制防止滥用
4. **文件验证**: 验证上传文件的安全性和大小限制
5. **HTTPS传输**: 使用HTTPS传输敏感数据
6. **日志记录**: 记录API调用日志便于审计

## 📞 联系方式

如有问题请查看：
- API文档: http://localhost:8765/docs
- 健康检查: http://localhost:8765/health 