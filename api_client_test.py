"""
API客户端测试脚本
用于测试Dolphin API服务的各个接口
"""

import base64
import json
import os
import requests
from pathlib import Path

from dotenv import load_dotenv


class DolphinAPIClient:
    def __init__(self, base_url: str = "http://localhost:8765", api_key: str = None):
        """
        初始化API客户端
        
        Args:
            base_url: API服务器的基础URL
            api_key: API认证密钥（可选）
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def image_to_base64(self, image_path: str) -> str:
        """将图像文件转换为base64字符串"""
        with open(image_path, "rb") as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode('utf-8')
    
    def health_check(self):
        """健康检查"""
        try:
            response = requests.get(f"{self.base_url}/health", headers=self.headers)
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def parse_page_base64(self, image_path: str, max_batch_size: int = 4):
        """
        使用base64编码的图像进行页面级解析
        
        Args:
            image_path: 图像文件路径
            max_batch_size: 最大批次大小
        """
        try:
            image_base64 = self.image_to_base64(image_path)
            
            payload = {
                "image_base64": image_base64,
                "max_batch_size": max_batch_size
            }
            
            headers = {"Content-Type": "application/json"}
            headers.update(self.headers)
            
            response = requests.post(
                f"{self.base_url}/parse_page",
                json=payload,
                headers=headers
            )
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def parse_element_base64(self, image_path: str, element_type: str):
        """
        使用base64编码的图像进行元素级解析
        
        Args:
            image_path: 图像文件路径  
            element_type: 元素类型 (text, table, formula)
        """
        try:
            image_base64 = self.image_to_base64(image_path)
            
            payload = {
                "image_base64": image_base64,
                "element_type": element_type
            }
            
            headers = {"Content-Type": "application/json"}
            headers.update(self.headers)
            
            response = requests.post(
                f"{self.base_url}/parse_element",
                json=payload,
                headers=headers
            )
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def upload_parse_page(self, image_path: str, max_batch_size: int = 4):
        """
        通过文件上传进行页面级解析
        
        Args:
            image_path: 图像文件路径
            max_batch_size: 最大批次大小
        """
        try:
            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                data = {"max_batch_size": max_batch_size}
                
                response = requests.post(
                    f"{self.base_url}/upload_parse_page",
                    files=files,
                    data=data,
                    headers=self.headers
                )
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def upload_parse_element(self, image_path: str, element_type: str):
        """
        通过文件上传进行元素级解析
        
        Args:
            image_path: 图像文件路径
            element_type: 元素类型 (text, table, formula)
        """
        try:
            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                data = {"element_type": element_type}
                
                response = requests.post(
                    f"{self.base_url}/upload_parse_element", 
                    files=files,
                    data=data,
                    headers=self.headers
                )
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}


def main():
    """主函数 - 运行测试"""
    import argparse
    
    # 加载.env.local文件
    load_dotenv('.env.local')
    
    parser = argparse.ArgumentParser(description="Dolphin API客户端测试")
    parser.add_argument("--url", default="http://localhost:8765", help="API服务器URL")
    parser.add_argument("--image", help="测试图像路径")
    parser.add_argument("--test-type", choices=["health", "page", "element"], 
                       default="health", help="测试类型")
    parser.add_argument("--element-type", choices=["text", "table", "formula"], 
                       default="text", help="元素类型（仅用于element测试）")
    parser.add_argument("--upload", action="store_true", help="使用文件上传方式")
    parser.add_argument("--api-key", help="API认证密钥（优先级高于.env.local文件）")
    parser.add_argument("--no-env", action="store_true", help="不从.env.local文件读取API Key")
    args = parser.parse_args()
    
    # 确定API Key
    api_key = None
    if args.api_key:
        api_key = args.api_key
        print("🔑 使用命令行指定的API Key")
    elif not args.no_env:
        env_keys_str = os.getenv('API_KEYS', '')
        if env_keys_str:
            # 使用第一个API Key
            env_keys = [key.strip() for key in env_keys_str.replace(',', ' ').split() if key.strip()]
            if env_keys:
                api_key = env_keys[0]
                print(f"📄 使用.env.local文件中的API Key（共{len(env_keys)}个，使用第一个）")
    
    if not api_key:
        print("⚠️  未设置API Key，将尝试无认证访问")
    
    # 创建客户端
    client = DolphinAPIClient(args.url, api_key)
    
    print(f"🔗 连接到API服务器: {args.url}")
    
    if args.test_type == "health":
        print("\n🏥 执行健康检查...")
        result = client.health_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.test_type == "page":
        if not args.image:
            print("❌ 页面级解析需要指定--image参数")
            return
        
        print(f"\n📄 执行页面级解析: {args.image}")
        if args.upload:
            print("📤 使用文件上传方式...")
            result = client.upload_parse_page(args.image)
        else:
            print("📋 使用base64方式...")
            result = client.parse_page_base64(args.image)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.test_type == "element":
        if not args.image:
            print("❌ 元素级解析需要指定--image参数")
            return
        
        print(f"\n🧩 执行元素级解析: {args.image} (类型: {args.element_type})")
        if args.upload:
            print("📤 使用文件上传方式...")
            result = client.upload_parse_element(args.image, args.element_type)
        else:
            print("📋 使用base64方式...")
            result = client.parse_element_base64(args.image, args.element_type)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main() 