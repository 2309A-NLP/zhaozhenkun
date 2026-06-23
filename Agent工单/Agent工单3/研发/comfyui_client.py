# -*- coding: utf-8 -*-
"""
ComfyUI API 客户端核心模块 — 服务器连接、工作流提交、结果获取、图像上传/下载。
扩展方法（姿态/高级工作流/辅助函数）通过子模块 monkeypatch 注册，
from comfyui_client import ComfyUIClient 即可获得完整功能。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
"""

import json
import logging
import os
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image

from config import strong_control_config

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"  # 默认服务器地址
DEFAULT_TIMEOUT = 600       # 单次生成超时（秒）
DEFAULT_POLL_INTERVAL = 1.0  # 轮询间隔（秒）


class ComfyUIClient:
    """ComfyUI API 客户端 — POST /prompt 提交工作流，GET /history 查询结果，GET /view 下载图像。"""

    def __init__(self, base_url=DEFAULT_COMFYUI_URL, timeout=DEFAULT_TIMEOUT,
                 poll_interval=DEFAULT_POLL_INTERVAL):
        """初始化客户端。base_url: 服务器地址; timeout: 超时秒数; poll_interval: 轮询间隔。"""
        self.base_url = base_url.rstrip("/")  # 去除末尾斜杠
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.client_id = str(uuid.uuid4())  # 唯一客户端标识
        self._ws = None  # WebSocket 预留
        logger.info(f"ComfyUI 客户端初始化: {self.base_url} (client_id={self.client_id[:8]}...)")

    # ================================================================
    # 服务器连接
    # ================================================================
    def check_health(self) -> bool:
        """检查服务器是否在线。"""
        try:
            resp = requests.get(f"{self.base_url}/system_stats", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def wait_for_server(self, timeout=120) -> bool:
        """等待服务器就绪，timeout 超时秒数。"""
        start = time.time()
        while time.time() - start < timeout:
            if self.check_health():
                logger.info(f"ComfyUI 服务器已就绪 (等待 {time.time() - start:.1f}s)")
                return True
            elapsed = time.time() - start
            logger.info(f"等待 ComfyUI 启动... ({elapsed:.0f}s/{timeout}s)")
            time.sleep(5)  # 每 5 秒重试
        logger.error(f"ComfyUI 服务器在 {timeout}s 内未就绪")
        return False

    # ================================================================
    # 工作流提交与执行
    # ================================================================
    def queue_prompt(self, workflow: Dict[str, Any]) -> Optional[str]:
        """提交工作流到队列，返回 prompt_id 用于查询状态。workflow 需为 API 对象格式。"""
        payload = {"prompt": workflow, "client_id": self.client_id}
        try:
            resp = requests.post(f"{self.base_url}/prompt", json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            prompt_id = result.get("prompt_id")
            if not prompt_id:  # 服务器未返回有效 ID
                logger.error(f"提交工作流失败，响应中缺少 prompt_id: {result}")
                return None
            logger.info(f"工作流已提交, prompt_id={prompt_id}")
            return prompt_id
        except requests.exceptions.HTTPError as e:
            response_text = ""
            try:
                response_text = e.response.text
            except Exception:
                pass
            logger.error(f"提交工作流 HTTP 异常: {e}")
            if response_text:
                logger.error(f"ComfyUI 返回内容: {response_text}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"无法连接到 ComfyUI ({self.base_url})，请确认 ComfyUI 已启动")
            return None
        except Exception as e:
            logger.error(f"提交工作流异常: {e}")
            return None

    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """获取 prompt_id 的执行历史。未完成时返回 None。"""
        try:
            resp = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10)
            resp.raise_for_status()
            return resp.json().get(prompt_id)  # 提取目标条目
        except Exception as e:
            logger.debug(f"获取历史失败 ({prompt_id}): {e}")
            return None

    def wait_for_prompt(self, prompt_id: str, timeout=None) -> Optional[Dict[str, Any]]:
        """轮询等待工作流执行完成。timeout 默认使用实例 timeout。"""
        timeout = timeout or self.timeout
        start = time.time()
        while time.time() - start < timeout:
            history = self.get_history(prompt_id)  # 轮询
            if history is not None:  # 历史存在即完成
                elapsed = time.time() - start
                logger.info(f"工作流执行完成 (耗时 {elapsed:.1f}s)")
                return history
            time.sleep(self.poll_interval)
        logger.error(f"工作流执行超时 ({timeout}s), prompt_id={prompt_id}")
        return None

    def execute_workflow(self, workflow: Dict[str, Any], timeout=None) -> Optional[Dict[str, Any]]:
        """提交工作流并等待完成（queue + wait 组合）。"""
        prompt_id = self.queue_prompt(workflow)
        if prompt_id is None:
            return None
        return self.wait_for_prompt(prompt_id, timeout=timeout)

    # ================================================================
    # 输出下载
    # ================================================================
    def get_output_images(self, history: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从执行历史提取输出图像元信息列表。"""
        outputs = []
        if "outputs" not in history:
            logger.warning("执行历史中没有 outputs 字段")
            return outputs
        for node_id, node_output in history["outputs"].items():
            if "images" not in node_output:
                continue
            for img_info in node_output["images"]:
                outputs.append({"filename": img_info["filename"],
                                "subfolder": img_info.get("subfolder", ""),
                                "type": img_info.get("type", "output"),
                                "node_id": node_id})
        logger.info(f"从 history 中提取到 {len(outputs)} 个输出图像")
        return outputs

    def download_image(self, filename, subfolder="", image_type="output") -> Optional[bytes]:
        """下载单个输出图像的原始字节。"""
        params = {"filename": filename, "subfolder": subfolder, "type": image_type}
        url = f"{self.base_url}/view?{urllib.parse.urlencode(params)}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.content  # 返回字节
        except Exception as e:
            logger.error(f"下载图像失败 ({filename}): {e}")
            return None

    def download_outputs(self, history, output_dir, prefix="output", filename_prefix="") -> List[str]:
        """下载所有输出图像到本地目录，返回已保存路径列表。"""
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        images = self.get_output_images(history)
        if filename_prefix:  # 按文件名前缀筛选
            images = [img for img in images
                      if str(img.get("filename", "")).startswith(filename_prefix)]
            logger.info(f"按前缀 {filename_prefix} 筛选后剩余 {len(images)} 个输出图像")
        for i, img_info in enumerate(images):
            data = self.download_image(img_info["filename"],
                                       img_info.get("subfolder", ""),
                                       img_info.get("type", "output"))
            if data is None:
                continue
            ext = os.path.splitext(img_info["filename"])[1] or ".png"
            local_path = os.path.join(output_dir, f"{prefix}_{i}{ext}")
            with open(local_path, "wb") as f:
                f.write(data)
            saved_paths.append(local_path)
            logger.info(f"已下载: {local_path}")
        return saved_paths

    # ================================================================
    # 图像上传
    # ================================================================
    def upload_image(self, image_data, filename=None, overwrite=True) -> Optional[str]:
        """上传图像字节到 ComfyUI input 目录，返回服务端文件名。"""
        if filename is None:
            filename = f"upload_{uuid.uuid4().hex[:8]}.png"  # 自动生成
        form_data = {"image": (filename, image_data, "image/png")}
        try:
            resp = requests.post(f"{self.base_url}/upload/image?overwrite=true",
                                 files=form_data, timeout=30)
            resp.raise_for_status()
            uploaded_name = resp.json().get("name", filename)
            logger.info(f"图像已上传: {uploaded_name}")
            return uploaded_name
        except Exception as e:
            logger.error(f"上传图像失败: {e}")
            return None

    def upload_image_from_path(self, image_path, overwrite=True) -> Optional[str]:
        """从本地路径读取图像并上传。"""
        with open(image_path, "rb") as f:
            data = f.read()
        return self.upload_image(data, filename=os.path.basename(image_path), overwrite=overwrite)


# ================================================================
# 延迟加载扩展方法（monkeypatch 注册入口）
# 以下 import 触发子模块将姿态/高级工作流/辅助方法附加到 ComfyUIClient
# ================================================================
from comfyui_pose import *       # noqa: E402, F403
from comfyui_workflow import *   # noqa: E402, F403
from comfyui_helpers import *    # noqa: E402, F403
