#!/usr/bin/env python3
"""
RAGFlow 工单17 - 自动化测试脚本
将功能验证和压测结果输出到指定目录
"""
import json
import os
import subprocess
import sys
import time
import requests

BASE_URL = "http://localhost:9380"
OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_jwt_token():
    """Generate valid JWT token using itsdangerous locally."""
    try:
        from itsdangerous import URLSafeTimedSerializer
    except ImportError:
        print("需要安装 itsdangerous: pip install itsdangerous")
        sys.exit(1)

    # RAGFlow secret key (from container settings)
    secret_key = "e320cfb2849c37ebc118ebc4b7b50c5df509cc47abc2de14ea969add968ade28"
    s = URLSafeTimedSerializer(secret_key=secret_key)
    # admin user's access_token
    access_token = "86dbe25e657211f192d1b16d9fc9c7ec"
    return s.dumps(access_token)


def api_get(path, token):
    """Make authenticated GET request."""
    r = requests.get(f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"})
    return r.status_code, r.json()


def api_post(path, token, data):
    """Make authenticated POST request."""
    r = requests.post(f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=data)
    return r.status_code, r.json()


def main():
    print("=" * 60)
    print("RAGFlow 工单17 - 自动化测试")
    print("=" * 60)

    # 1. Get JWT token
    print("\n[1/5] 生成JWT Token...")
    token = get_jwt_token()
    print(f"  Token: {token[:40]}...")

    # 2. Check existing resources
    print("\n[2/5] 探查已有资源...")
    code, data = api_get("/api/v1/chats", token)
    if code == 200:
        dd = data.get("data", [])
        if isinstance(dd, list):
            chats = dd
        else:
            chats = dd.get("chats", [])
        print(f"  已有Chat数: {len(chats)}")
        for c in chats[:3]:
            print(f"    - {c.get('name', 'N/A')} (id={c.get('id', 'N/A')})")
    else:
        print(f"  获取Chat列表失败: {data}")

    code, data = api_get("/api/v1/datasets", token)
    if code == 200:
        dd = data.get("data", [])
        if isinstance(dd, list):
            datasets = dd
        else:
            datasets = dd.get("datasets", [])
        print(f"  已有数据集数: {len(datasets)}")
        for d in datasets[:3]:
            print(f"    - {d.get('name', 'N/A')} (id={d.get('id', 'N/A')})")
    else:
        print(f"  获取数据集失败 (code={code}): {data.get('message','')}")

    # 3. Health check
    print("\n[3/5] 健康检查...")
    r = requests.get(f"{BASE_URL}/api/v1/system/healthz")
    print(f"  Status: {r.status_code}")
    health = r.json()
    for k, v in health.items():
        status = "✅" if v else "❌"
        print(f"  {status} {k}")

    # 4. Save baseline environment info
    print("\n[4/5] 采集环境基准数据...")
    env_info = {}
    try:
        result = subprocess.run(["docker", "stats", "--no-stream",
            "docker-ragflow-cpu-1", "docker-mysql-1", "docker-es01-1", "docker-redis-1"],
            capture_output=True, text=True, timeout=10)
        env_info["docker_stats"] = result.stdout
        print("  Docker stats collected")
    except Exception as e:
        print(f"  Docker stats failed: {e}")

    # Memory info
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        env_info["memory"] = result.stdout
        print(f"  Memory: {result.stdout.splitlines()[1] if len(result.stdout.splitlines()) > 1 else 'N/A'}")
    except Exception:
        pass

    with open(f"{OUTPUT_DIR}/environment_baseline.json", "w") as f:
        json.dump(env_info, f, indent=2, ensure_ascii=False)
    print("  基准数据已保存")

    # 5. Quick functional test
    print("\n[5/5] 功能验证...")

    # Test listing chats
    code, data = api_get("/api/v1/chats", token)
    functional_ok = (code == 200)
    print(f"  API连通性: {'✅' if functional_ok else '❌'} (code={code})")

    # Summary
    print("\n" + "=" * 60)
    print("环境准备完成！")
    print(f"JWT Token已就绪，可运行JMeter压测")
    print(f"JMeter脚本位置: {OUTPUT_DIR}/")
    print(f"  - 测试/jmeter_scenario_a_qa_5concurrent.jmx")
    print(f"  - 测试/jmeter_scenario_b_mixed_3concurrent.jmx")
    print(f"  - 测试/jmeter_scenario_a_20concurrent.jmx")
    print(f"  - 测试/jmeter_scenario_b_10concurrent.jmx")
    print("=" * 60)

    # Save token for JMeter
    with open(f"{OUTPUT_DIR}/.jwt_token", "w") as f:
        f.write(token)
    print(f"\nToken已保存到 {OUTPUT_DIR}/.jwt_token")

    return 0


if __name__ == "__main__":
    sys.exit(main())
