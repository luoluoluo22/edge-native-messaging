#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import time
import uuid

# 服务器地址
BASE_URL = "http://localhost:8888"

def print_response(response):
    """打印响应信息"""
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    try:
        data = response.json()
        # 如果响应中有markdown，且长度很长，只打印一部分
        if "markdown" in data and len(data["markdown"]) > 1000:
            # 保存完整的markdown到文件
            markdown_content = data["markdown"]
            filename = f"markdown_{int(time.time())}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            print(f"Markdown内容过长，已保存到文件: {filename}")
            
            # 在响应中只打印前1000个字符
            data["markdown"] = f"{data['markdown'][:1000]}... (截断，完整内容见文件)"
        
        print(f"响应内容: {json.dumps(data, ensure_ascii=False, indent=2)}")
    except:
        print(f"响应内容: {response.text}")
    print("-" * 50)

def test_index():
    """测试首页接口"""
    print("\n测试首页接口...")
    response = requests.get(f"{BASE_URL}/")
    print_response(response)
    return response.status_code == 200

def test_send_notification():
    """测试发送通知接口"""
    print("\n测试发送通知接口...")
    data = {
        "message": f"测试通知消息 - {time.strftime('%H:%M:%S')}"
    }
    response = requests.post(
        f"{BASE_URL}/api/send-notification",
        json=data
    )
    print_response(response)
    return response.status_code == 200

def test_get_page_source():
    """测试获取页面源码接口"""
    print("\n测试获取页面源码接口...")
    request_id = f"test_{uuid.uuid4().hex[:8]}"
    data = {
        "request_id": request_id
    }
    response = requests.post(
        f"{BASE_URL}/api/get-page-source",
        json=data
    )
    print_response(response)
    
    # 等待一会儿再检查结果
    if response.status_code == 200:
        print(f"等待3秒后检查页面源码请求结果...")
        time.sleep(3)
        success = test_page_source_result(request_id)
        
        # 如果获取到了源码，也测试一下Markdown转换功能
        if success:
            time.sleep(2)  # 等待后台转换完成
            print(f"测试Markdown转换功能...")
            test_get_markdown(request_id)
            
        return success
    return False

def test_page_source_result(request_id):
    """测试获取页面源码结果接口"""
    print("\n测试获取页面源码结果接口...")
    data = {
        "request_id": request_id
    }
    response = requests.post(
        f"{BASE_URL}/api/page-source-result",
        json=data
    )
    print_response(response)
    return response.status_code == 200

def test_get_markdown(request_id):
    """测试获取Markdown格式内容接口"""
    print("\n测试获取Markdown内容接口...")
    data = {
        "request_id": request_id
    }
    response = requests.post(
        f"{BASE_URL}/api/get-markdown",
        json=data
    )
    print_response(response)
    
    if response.status_code == 200:
        try:
            result = response.json()
            if result.get("status") == "success" and "markdown" in result:
                print(f"成功获取Markdown内容，长度: {result.get('markdown_length', 0)}")
                return True
        except:
            pass
    
    print("获取Markdown内容失败")
    return False

def run_all_tests():
    """运行所有测试"""
    results = {}
    
    print("开始测试HTTP服务...")
    print("=" * 50)
    
    # 测试首页
    results["首页接口"] = test_index()
    
    # 测试发送通知
    results["发送通知接口"] = test_send_notification()
    
    # 测试获取页面源码及结果
    results["获取页面源码接口"] = test_get_page_source()
    
    # 单独测试Markdown接口 (使用已知的请求ID)
    print("\n是否要测试指定ID的Markdown转换? (y/n)")
    choice = input().strip().lower()
    if choice == 'y':
        request_id = input("请输入已知的请求ID: ").strip()
        if request_id:
            results["Markdown转换接口"] = test_get_markdown(request_id)
    
    # 打印测试结果摘要
    print("\n测试结果摘要:")
    print("=" * 50)
    for test_name, result in results.items():
        status = "通过" if result else "失败"
        print(f"{test_name}: {status}")
    
    # 计算通过率
    pass_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    pass_rate = (pass_count / total_count) * 100 if total_count > 0 else 0
    
    print(f"\n测试完成! 通过率: {pass_rate:.2f}% ({pass_count}/{total_count})")

if __name__ == "__main__":
    try:
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print("连接错误: 无法连接到服务器。请确保服务正在运行。")
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}") 
 