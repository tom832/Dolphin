"""
API服务器 - 将Dolphin模型包装成网络API服务
支持页面级和元素级文档解析
"""

import argparse
import base64
import io
import os
import time
from typing import List, Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv

import cv2
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from omegaconf import OmegaConf
from PIL import Image
from pydantic import BaseModel

from chat import DOLPHIN
from utils.utils import crop_margin, prepare_image, parse_layout_string, process_coordinates

import logging

class ParsePageRequest(BaseModel):
    """页面级解析请求"""
    image_base64: str
    max_batch_size: Optional[int] = 1


class ParseElementRequest(BaseModel):
    """元素级解析请求"""
    image_base64: str
    element_type: str  # text, table, formula


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    message: str
    results: Optional[List[dict]] = None
    processing_time: Optional[float] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """在应用启动时执行唯一的初始化"""
    print("🚀 服务启动中，开始初始化...")
    load_dotenv('.env.local')

    # --- 配置完全来自于环境变量 ---
    config_path = os.getenv('DOLPHIN_CONFIG', './config/Dolphin.yaml')
    api_keys_str = os.getenv('API_KEYS', '')
    api_keys_file = os.getenv('API_KEYS_FILE')

    api_keys = []
    
    # 1. 从环境变量 "API_KEYS" 加载 (可以来自 .env 文件或命令行)
    if api_keys_str:
        keys = [key.strip() for key in api_keys_str.replace(',', ' ').split() if key.strip()]
        api_keys.extend(keys)
        print(f"🔑 从环境变量 'API_KEYS' 加载了 {len(keys)} 个API Keys")

    # 2. 从环境变量 "API_KEYS_FILE" 指定的文件加载
    if api_keys_file and os.path.exists(api_keys_file):
        with open(api_keys_file, 'r') as f:
            file_keys = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            api_keys.extend(file_keys)
            print(f"📁 从文件 {api_keys_file} 读取到 {len(file_keys)} 个API Keys")

    # 去重后初始化
    if api_keys:
        unique_keys = list(set(api_keys))
        init_api_keys(unique_keys)
        print(f"🔐 API Key认证已启用，总共加载 {len(unique_keys)} 个唯一的Keys。")
    else:
        print("⚠️  未设置API Key，认证已禁用（不推荐用于生产环境）")

    # 初始化模型
    print(f"🚀 正在从 {config_path} 初始化Dolphin模型...")
    init_model(config_path)

    yield
    
    print("👋 应用已关闭")


app = FastAPI(
    title="Dolphin Document Parser API",
    description="基于Dolphin模型的文档图像解析API服务",
    version="1.0.0",
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", "/dolphin")  # 可通过环境变量配置，默认为/dolphin（生产环境）
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量存储模型和配置
model = None
API_KEYS = set()  # 存储有效的API Keys
security = HTTPBearer()


def init_model(config_path: str):
    """初始化Dolphin模型"""
    global model
    try:
        config = OmegaConf.load(config_path)
        model = DOLPHIN(config)
        print("✅ Dolphin模型加载成功")
    except Exception as e:
        print(f"❌ 模型加载失败: {str(e)}")
        raise e


def init_api_keys(api_keys: List[str]):
    """初始化API Keys"""
    global API_KEYS
    API_KEYS = set(api_keys)
    print(f"✅ 已加载 {len(API_KEYS)} 个API Keys")


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    验证API Key
    支持两种格式：
    1. Bearer token: Authorization: Bearer your_api_key
    2. Custom header: X-API-Key: your_api_key
    """
    if not API_KEYS:
        # 如果没有设置API Keys，跳过验证
        return True
    
    token = credentials.credentials
    if token not in API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="无效的API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


def verify_api_key_header(x_api_key: str = Header(None, alias="X-API-Key")):
    """通过自定义Header验证API Key（备用方式）"""
    if not API_KEYS:
        return True
    
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="无效的API Key")
    return True


def base64_to_image(base64_str: str) -> Image.Image:
    """将base64字符串转换为PIL Image"""
    try:
        # 移除data:image前缀（如果存在）
        if base64_str.startswith('data:image'):
            base64_str = base64_str.split(',')[1]
        
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        return image
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图像解码失败: {str(e)}")


def process_page_api(pil_image: Image.Image, max_batch_size: int):
    """API版本的页面级解析"""
    try:
        # Stage 1: 页面级布局和阅读顺序解析
        layout_output = model.chat("Parse the reading order of this document.", pil_image)
        
        # Stage 2: 元素级内容解析
        padded_image, dims = prepare_image(pil_image)
        recognition_results = process_elements_api(layout_output, padded_image, dims, max_batch_size)
        
        return recognition_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"页面解析失败: {str(e)}")


def process_elements_api(layout_results, padded_image, dims, max_batch_size):
    """API版本的元素处理"""
    layout_results = parse_layout_string(layout_results)
    
    text_table_elements = []
    figure_results = []
    previous_box = None
    reading_order = 0
    
    # 收集需要处理的元素
    for bbox, label in layout_results:
        try:
            # 调整坐标
            x1, y1, x2, y2, orig_x1, orig_y1, orig_x2, orig_y2, previous_box = process_coordinates(
                bbox, padded_image, dims, previous_box
            )
            
            # 裁剪和解析元素
            cropped = padded_image[y1:y2, x1:x2] 
            if cropped.size > 0:
                if label == "fig":
                    figure_results.append({
                        "label": label,
                        "bbox": [orig_x1, orig_y1, orig_x2, orig_y2],
                        "text": "",
                        "reading_order": reading_order,
                    })
                else:
                    pil_crop = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
                    prompt = "Parse the table in the image." if label == "tab" else "Read text in the image."
                    text_table_elements.append({
                        "crop": pil_crop,
                        "prompt": prompt,
                        "label": label,
                        "bbox": [orig_x1, orig_y1, orig_x2, orig_y2],
                        "reading_order": reading_order,
                    })
            
            reading_order += 1
            
        except Exception as e:
            print(f"处理bbox时出错，标签为 {label}: {str(e)}")
            continue
    
    # 并行解析文本/表格元素
    recognition_results = figure_results
    if text_table_elements:
        crops_list = [elem["crop"] for elem in text_table_elements]
        prompts_list = [elem["prompt"] for elem in text_table_elements]
        
        # 批量推理
        # 为了节省显存，这里max_batch_size=1
        max_batch_size = 1
        batch_results = model.chat(prompts_list, crops_list, max_batch_size=max_batch_size)
        
        # 添加批量结果到recognition_results
        for i, result in enumerate(batch_results):
            elem = text_table_elements[i]
            recognition_results.append({
                "label": elem["label"],
                "bbox": elem["bbox"],
                "text": result.strip(),
                "reading_order": elem["reading_order"],
            })
    
    # 按阅读顺序排序
    recognition_results.sort(key=lambda x: x.get("reading_order", 0))
    
    return recognition_results


def process_element_api(pil_image: Image.Image, element_type: str):
    """API版本的元素级解析"""
    try:
        # 裁剪边缘
        pil_image = crop_margin(pil_image)
        
        # 根据元素类型选择合适的提示
        if element_type == "table":
            prompt = "Parse the table in the image."
            label = "tab"
        elif element_type == "formula":
            prompt = "Read text in the image."
            label = "formula"
        else:  # 默认为文本
            prompt = "Read text in the image."
            label = "text"
        
        # 处理元素
        result = model.chat(prompt, pil_image)
        
        # 创建识别结果
        recognition_result = [{
            "label": label,
            "text": result.strip(),
        }]
        
        return recognition_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"元素解析失败: {str(e)}")


@app.get("/")
async def root():
    """根路径 - API信息"""
    return {
        "message": "Dolphin Document Parser API",
        "version": "1.0.0",
        "endpoints": {
            "parse_page": "/parse_page - 页面级文档解析",
            "parse_element": "/parse_element - 元素级解析",
            "upload_parse_page": "/upload_parse_page - 上传文件进行页面级解析",
            "upload_parse_element": "/upload_parse_element - 上传文件进行元素级解析"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "timestamp": time.time()
    }


@app.post("/parse_page", response_model=ParseResponse)
async def parse_page(request: ParsePageRequest, _: bool = Depends(verify_api_key)):
    """页面级文档解析"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未初始化")
    
    start_time = time.time()
    
    try:
        # 解码图像
        pil_image = base64_to_image(request.image_base64)
        
        # 执行页面级解析
        results = process_page_api(pil_image, request.max_batch_size)
        
        processing_time = time.time() - start_time
        
        return ParseResponse(
            success=True,
            message="页面解析成功",
            results=results,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ParseResponse(
            success=False,
            message=f"解析失败: {str(e)}",
            processing_time=time.time() - start_time
        )


@app.post("/parse_element", response_model=ParseResponse)
async def parse_element(request: ParseElementRequest, _: bool = Depends(verify_api_key)):
    """元素级解析"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未初始化")
    
    # 验证元素类型
    if request.element_type not in ["text", "table", "formula"]:
        raise HTTPException(status_code=400, detail="element_type必须是text、table或formula之一")
    
    start_time = time.time()
    
    try:
        # 解码图像
        pil_image = base64_to_image(request.image_base64)
        
        # 执行元素级解析
        results = process_element_api(pil_image, request.element_type)
        
        processing_time = time.time() - start_time
        
        return ParseResponse(
            success=True,
            message="元素解析成功",
            results=results,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ParseResponse(
            success=False,
            message=f"解析失败: {str(e)}",
            processing_time=time.time() - start_time
        )


@app.post("/upload_parse_page", response_model=ParseResponse)
async def upload_parse_page(
    file: UploadFile = File(...),
    max_batch_size: int = Form(4),
    _: bool = Depends(verify_api_key)
):
    """上传文件进行页面级解析"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未初始化")
    
    # 验证文件是否存在
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="未提供有效文件")
    
    # 验证文件类型（更健壮的验证）
    if file.content_type and not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="文件必须是图像格式")
    
    # 如果content_type为None，通过文件扩展名验证
    if not file.content_type:
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="不支持的文件格式，请上传图像文件")
    
    start_time = time.time()
    
    try:
        # 读取上传的文件
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="文件内容为空")
            
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 执行页面级解析  
        results = process_page_api(pil_image, max_batch_size)
        
        processing_time = time.time() - start_time
        
        return ParseResponse(
            success=True,
            message="页面解析成功",
            results=results,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ParseResponse(
            success=False,
            message=f"解析失败: {str(e)}",
            processing_time=time.time() - start_time
        )


@app.post("/upload_parse_element", response_model=ParseResponse)
async def upload_parse_element(
    file: UploadFile = File(...),
    element_type: str = Form(...),
    _: bool = Depends(verify_api_key)
):
    """上传文件进行元素级解析"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未初始化")
    
    # 验证文件是否存在
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="未提供有效文件")
    
    # 验证文件类型（更健壮的验证）
    if file.content_type and not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="文件必须是图像格式")
    
    # 如果content_type为None，通过文件扩展名验证
    if not file.content_type:
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="不支持的文件格式，请上传图像文件")
    
    # 验证元素类型
    if element_type not in ["text", "table", "formula"]:
        raise HTTPException(status_code=400, detail="element_type必须是text、table或formula之一")
    
    start_time = time.time()
    
    try:
        # 读取上传的文件
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="文件内容为空")
            
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 执行元素级解析
        results = process_element_api(pil_image, element_type)
        
        processing_time = time.time() - start_time
        
        return ParseResponse(
            success=True,
            message="元素解析成功",
            results=results,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return ParseResponse(
            success=False,
            message=f"解析失败: {str(e)}",
            processing_time=time.time() - start_time
        )


def main():
    """
    服务器启动入口。
    此函数解析命令行参数，设置相应的环境变量，然后启动Uvicorn服务器。
    所有初始化逻辑均在lifespan事件中处理，以避免在主进程中重复加载。
    """
    # 首先加载.env文件，这样命令行参数可以覆盖它
    load_dotenv('.env.local')

    # 配置日志格式，包含时间信息
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
        # 配置 uvicorn 日志格式
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
    }
    
    parser = argparse.ArgumentParser(
        description="Dolphin API Server Launcher.\n\n"
                    "通过 `python api_server.py` 启动时，可以使用所有命令行参数。\n"
                    "如果直接使用 `uvicorn`，请手动设置环境变量: \n"
                    "DOLPHIN_CONFIG, API_KEYS, API_KEYS_FILE.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Uvicorn相关参数
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="服务器主机地址")
    parser.add_argument("--port", type=int, default=os.getenv("PORT", 8765), help="服务器端口")
    parser.add_argument("--workers", type=int, default=os.getenv("WORKERS", 1), help="工作进程数")
    
    # 应用配置参数
    parser.add_argument("--config", default=os.getenv('DOLPHIN_CONFIG', './config/Dolphin.yaml'), help="模型配置文件路径")
    parser.add_argument("--api-keys", nargs="*", default=None, help="API Keys列表，用空格分隔。会覆盖.env中的设置。")
    parser.add_argument("--api-keys-file", default=os.getenv('API_KEYS_FILE'), help="包含API Keys的文件路径。")
    parser.add_argument("--root-path", default=os.getenv('ROOT_PATH', '/dolphin'), help="API根路径前缀，用于反向代理部署。")
    
    args = parser.parse_args()

    # --- 将命令行参数设置到环境变量，传递给Uvicorn工作进程 ---
    os.environ['DOLPHIN_CONFIG'] = args.config
    os.environ['ROOT_PATH'] = args.root_path
    
    # 只有当命令行提供了--api-keys时才覆盖环境变量
    if args.api_keys is not None:
        os.environ['API_KEYS'] = " ".join(args.api_keys)
        
    if args.api_keys_file:
        os.environ['API_KEYS_FILE'] = args.api_keys_file
    
    # 启动服务器
    print(f"🌟 启动API服务器 (通过启动器脚本)...")
    print(f"   - Host: {args.host}")
    print(f"   - Port: {args.port}")
    print(f"   - Workers: {args.workers}")
    print(f"   - Config: {os.environ.get('DOLPHIN_CONFIG')}")
    print(f"📚 API文档: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=False,
        log_config=log_config
    )


if __name__ == "__main__":
    main() 