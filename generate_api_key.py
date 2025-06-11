#!/usr/bin/env python3
"""
API Key生成工具
用于生成安全的随机API Key
"""

import argparse
import secrets
import uuid


def generate_hex_key(length=32):
    """生成十六进制API Key"""
    return secrets.token_hex(length)


def generate_uuid_key():
    """生成UUID格式的API Key"""
    return uuid.uuid4().hex


def generate_urlsafe_key(length=43):
    """生成URL安全的base64格式API Key"""
    return secrets.token_urlsafe(length)


def main():
    parser = argparse.ArgumentParser(description="生成API Key")
    parser.add_argument("--count", "-c", type=int, default=1, help="生成API Key的数量")
    parser.add_argument("--type", "-t", choices=["hex", "uuid", "urlsafe"], 
                       default="hex", help="API Key类型")
    parser.add_argument("--length", "-l", type=int, default=32, 
                       help="API Key长度（仅适用于hex和urlsafe类型）")
    parser.add_argument("--output", "-o", help="输出到文件")
    parser.add_argument("--env", action="store_true", help="输出.env.local格式")
    args = parser.parse_args()
    
    # 生成API Keys
    api_keys = []
    for _ in range(args.count):
        if args.type == "hex":
            key = generate_hex_key(args.length)
        elif args.type == "uuid":
            key = generate_uuid_key()
        elif args.type == "urlsafe":
            key = generate_urlsafe_key(args.length)
        api_keys.append(key)
    
    # 输出结果
    if args.env:
        # 输出.env.local格式
        output = f"API_KEYS={','.join(api_keys)}\n"
    else:
        # 每行一个API Key
        output = '\n'.join(api_keys) + '\n'
    
    if args.output:
        # 写入文件
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"✅ 已生成 {args.count} 个API Key并保存到 {args.output}")
    else:
        # 输出到控制台
        print(f"🔑 生成的API Key ({args.type}格式):")
        print(output.rstrip())


if __name__ == "__main__":
    main() 