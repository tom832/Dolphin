#!/bin/bash

# Dolphin API服务器启动脚本

# 设置环境变量
export CUDA_VISIBLE_DEVICES=1

# 默认参数
CONFIG_PATH="./config/Dolphin.yaml"
HOST="0.0.0.0"
PORT=8765
WORKERS=1

# 检查配置文件是否存在
if [ ! -f "$CONFIG_PATH" ]; then
    echo "❌ 配置文件不存在: $CONFIG_PATH"
    echo "请确保已下载模型文件并正确配置"
    exit 1
fi

# 检查模型文件是否存在
if [ ! -d "./checkpoints" ] && [ ! -d "./hf_model" ]; then
    echo "❌ 模型文件未找到"
    echo "请确保已下载模型文件到 ./checkpoints 或 ./hf_model 目录"
    exit 1
fi

# 检查.env.local文件
if [ -f ".env.local" ]; then
    echo "📄 发现.env.local文件，将从中读取API Keys"
else
    echo "⚠️  未找到.env.local文件，请参考env_example.txt创建"
fi

echo "🚀 启动Dolphin API服务器..."
echo "📁 配置文件: $CONFIG_PATH"
echo "🌐 监听地址: $HOST:$PORT"
echo "⚡ 工作进程: $WORKERS"
echo ""

# 启动服务器
python api_server.py \
    --config "$CONFIG_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" 