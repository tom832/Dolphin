#!/bin/bash

# Dolphin API服务器环境配置脚本
# 快速设置.env.local文件

echo "🔧 Dolphin API服务器环境配置"
echo "================================"

# 检查是否已存在.env.local文件
if [ -f ".env.local" ]; then
    echo "⚠️  发现已存在的.env.local文件"
    read -p "是否要覆盖现有文件？(y/N): " overwrite
    if [[ ! $overwrite =~ ^[Yy]$ ]]; then
        echo "❌ 取消操作"
        exit 0
    fi
fi

echo ""
echo "请选择配置方式："
echo "1) 自动生成API Keys（推荐）"
echo "2) 手动输入API Keys"
echo "3) 使用示例文件"

read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo ""
        read -p "请输入要生成的API Key数量 (默认: 3): " count
        count=${count:-3}
        
        echo "🔑 正在生成 $count 个API Keys..."
        python generate_api_key.py --count $count --env --output .env.local
        
        if [ $? -eq 0 ]; then
            echo "✅ .env.local文件已创建"
            echo ""
            echo "📄 文件内容："
            cat .env.local
        else
            echo "❌ 生成失败"
            exit 1
        fi
        ;;
    2)
        echo ""
        echo "请输入API Keys（用逗号或空格分隔）："
        read -p "API Keys: " api_keys
        
        if [ -z "$api_keys" ]; then
            echo "❌ API Keys不能为空"
            exit 1
        fi
        
        echo "# Dolphin API服务器环境配置文件" > .env.local
        echo "# 自动生成于 $(date)" >> .env.local
        echo "" >> .env.local
        echo "API_KEYS=$api_keys" >> .env.local
        
        echo "✅ .env.local文件已创建"
        echo ""
        echo "📄 文件内容："
        cat .env.local
        ;;
    3)
        if [ -f "env_example.txt" ]; then
            cp env_example.txt .env.local
            echo "✅ 已复制示例文件到.env.local"
            echo "⚠️  请编辑.env.local文件，设置真实的API Keys"
            echo ""
            echo "📝 编辑命令："
            echo "nano .env.local"
        else
            echo "❌ 示例文件env_example.txt不存在"
            exit 1
        fi
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "🎉 配置完成！"
echo ""
echo "📋 下一步："
echo "1. 启动服务: ./start_api_server.sh"
echo "2. 测试API: python api_client_test.py --test-type health"
echo "3. 查看文档: http://localhost:8765/docs" 