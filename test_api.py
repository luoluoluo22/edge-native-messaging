#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import sys

# API端点
API_URL = "http://localhost:8888"

def print_response(response):
    """打印响应内容"""
    try:
        print(f"状态码: {response.status_code}")
        data = response.json()
        
        # 如果响应中包含Markdown，只打印部分内容避免输出过长
        if "markdown" in data:
            md_length = len(data["markdown"])
            preview_length = min(200, md_length)
            data["markdown"] = data["markdown"][:preview_length] + f"... [省略 {md_length - preview_length} 字符]"
            
        print(f"响应内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"解析响应时出错: {str(e)}")
        print(f"原始响应: {response.text}")

def test_get_current_tab_markdown():
    """测试直接获取当前标签页Markdown内容"""
    print("\n===== 测试获取当前标签页Markdown内容 =====")
    try:
        # 发送请求获取当前标签页的Markdown
        url = f"{API_URL}/api/get-current-tab-markdown"
        
        print(f"发送请求到: {url}")
        
        response = requests.post(url, json={})
        print_response(response)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                # 可以选择将完整的Markdown保存到文件
                save_to_file = input("\n是否保存完整Markdown到文件？(y/n): ").strip().lower() == 'y'
                if save_to_file and "markdown" in data:
                    import time
                    filename = f"current_tab_markdown_{int(time.time())}.md"
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(data["markdown"])
                    print(f"Markdown已保存到文件: {filename}")
                    
                return True
            else:
                print(f"获取失败，状态: {data.get('status')}, 错误: {data.get('message')}")
                return False
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"测试获取当前标签页Markdown时出错: {str(e)}")
        return False

def test_api_status():
    """测试API服务状态"""
    print("\n===== 测试API服务状态 =====")
    try:
        response = requests.get(API_URL)
        print_response(response)
        return response.status_code == 200
    except Exception as e:
        print(f"测试API服务状态时出错: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始测试API...")
    
    # 先测试API服务状态
    api_available = test_api_status()
    
    if api_available:
        # 测试获取当前标签页Markdown内容
        test_get_current_tab_markdown()
    else:
        print("\n无法连接到API服务，请确保服务正在运行。")
    
    print("\n测试完成。") 