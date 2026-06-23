# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：强身份控制路线适配模块
==============================================================================
本模块不再假装“普通 img2img + prompt”可以稳定实现保脸转头，
而是明确区分：
1. 强控制路线：接入 ComfyUI / InstantID / IP-Adapter Face 工作流
2. 兜底路线：继续使用旧版生成器，仅作为预览，不承诺验收效果

核心目标：
- 对外提供统一接口，便于 Web/CLI 切换
- 在未配置强控制工作流时，给出明确提示，不误导用户
- 为后续接入 ComfyUI API / 工作流 JSON 预留稳定位置

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import copy
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np

from config import strong_control_config
from image_generator import ImageGenerator

logger = logging.getLogger(__name__)

# 延迟导入 ComfyUI 客户端（避免在未安装依赖时阻塞 import）
_comfyui_client_available = True
try:
    from comfyui_client import ComfyUIClient
except Exception as _comfyui_import_err:
    _comfyui_client_available = False
    ComfyUIClient = None
    logger.debug(f"ComfyUI 客户端未加载: {_comfyui_import_err}")


@dataclass
class RotationTask:
    """单个转头任务描述"""
    key: str
    label: str
    direction: str
    angle: float


class StrongControlRouter:
    """强控制路线入口

    优先走强控制工作流；若未就绪则可选择回退到旧版弱控制路线。
    """

    def __init__(self):
        self.tasks = [
            RotationTask("left", "左转(-30°)", "left", -30.0),
            RotationTask("right", "右转(+30°)", "right", 30.0),
            RotationTask("front", "端正(0°)", "front", 0.0),
        ]

    def get_route_report(self) -> Dict[str, str]:
        workflow_ready = self._is_workflow_ready()
        if workflow_ready:
            return {
                "route": "strong",
                "summary": "已检测到强控制工作流配置，走 ComfyUI/InstantID 路线。",
            }
        return {
            "route": "fallback",
            "summary": (
                "未检测到强控制工作流，当前只能回退到旧版弱控制路线。"
                "该路线能出图，但不保证还是同一个人，也不保证左右转角度严格达标。"
            ),
        }

    def generate_all_rotations(self, image: np.ndarray, processor=None) -> Dict[str, object]:
        if self._is_workflow_ready():
            return self._run_strong_workflow(image)
        if not strong_control_config.allow_fallback:
            raise RuntimeError(
                "强控制工作流未配置完成，且当前已禁用弱控制回退。"
                "请先补齐 ComfyUI 工作流 JSON 与输入输出目录。"
            )
        return self._run_fallback_pipeline(image, processor)

    def _is_workflow_ready(self) -> bool:
        # 基础要素：工作流 JSON 必须存在
        if not strong_control_config.workflow_path:
            return False
        if not os.path.exists(strong_control_config.workflow_path):
            logger.warning(
                f"强控制工作流文件不存在: {strong_control_config.workflow_path}"
            )
            return False
        # 工作流 JSON 不能是空的占位符
        with open(strong_control_config.workflow_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        # 检测 API 格式（key 为数字字符串）或旧 nodes 数组格式
        has_nodes = bool(workflow.get("nodes")) or any(
            isinstance(v, dict) and "class_type" in v
            for v in workflow.values()
        )
        if not has_nodes:
            logger.warning("强控制工作流 JSON 中无节点（仍是占位符），无法使用")
            return False
        # 检查 ComfyUI 客户端可用性
        if not _comfyui_client_available:
            logger.warning(
                "ComfyUI 客户端模块不可用，无法走强控制路线。"
                "请确认 comfyui_client.py 在 PYTHONPATH 中。"
            )
            return False
        return True

    def _run_strong_workflow(self, image: np.ndarray) -> Dict[str, object]:
        os.makedirs(strong_control_config.input_dir, exist_ok=True)
        os.makedirs(strong_control_config.output_dir, exist_ok=True)

        # 保存源图像
        from utils import load_image, save_image
        image_path = os.path.join(strong_control_config.input_dir, "source_face.png")
        success = save_image(image, image_path)
        if not success:
            raise RuntimeError(f"保存强控制输入图失败: {image_path}")

        # 初始化 ComfyUI 客户端
        client = ComfyUIClient(base_url=strong_control_config.comfyui_api_url)

        # 检查服务器是否在线
        if not client.check_health():
            msg = (
                f"ComfyUI 服务器未响应 ({strong_control_config.comfyui_api_url})。"
                f"\n请先启动 ComfyUI: cd /home/zzy/ComfyUI && python main.py --port 8188"
                f"\n源图像已保存到: {image_path}"
            )
            logger.warning(msg)
            if not strong_control_config.allow_fallback:
                raise RuntimeError(msg)
            # 回退 — 但需要先返回尝试信息
            return {
                "mode": "strong_offline",
                "images": [],
                "outpaint_images": [],
                "status": msg,
                "report": self.get_route_report(),
            }

        logger.info("ComfyUI 服务器在线，开始执行强控制工作流...")

        try:
            result = client.execute_workflow_with_faces(
                source_image_path=image_path,
                output_dir=strong_control_config.output_dir,
                workflow_path=strong_control_config.workflow_path,
            )
        except Exception as e:
            logger.error(f"ComfyUI 工作流执行异常: {e}")
            if not strong_control_config.allow_fallback:
                raise
            return self._run_fallback_pipeline(image)

        if not result["success"]:
            msg = (
                f"强控制工作流部分失败: {result['errors']}"
                f"\n已生成图像: {list(result['images'].keys())}"
            )
            logger.error(msg)
        else:
            msg = (
                "✅ 强控制路线执行成功（ComfyUI + IP-Adapter Face）。"
                "\n三姿态面部旋转已全部生成。"
            )

        # 加载生成的图像；不再用原图伪装“成功结果”
        images = []
        missing_keys = []
        for pose_key in ("left", "right", "front"):
            path = result["images"].get(pose_key)
            if path and os.path.exists(path):
                img = load_image(path)
                if img is not None:
                    images.append(img)
                    continue
                logger.warning(f"无法加载生成图像: {path}")
            else:
                logger.warning(f"缺少 {pose_key} 姿态图像")
            missing_keys.append(pose_key)

        if missing_keys:
            detail = f"强控制工作流未产出完整图像，缺少: {', '.join(missing_keys)}"
            if result.get("errors"):
                detail = f"{detail}\n错误详情: {' | '.join(result['errors'])}"
            logger.error(detail)
            return {
                "mode": "strong_failed",
                "images": [],
                "outpaint_images": [],
                "status": detail,
                "report": self.get_route_report(),
            }

        return {
            "mode": "strong",
            "images": images,
            "outpaint_images": [],
            "status": msg,
            "report": self.get_route_report(),
        }

    def _build_workflow_payload(self, image_path: str) -> Dict[str, object]:
        with open(strong_control_config.workflow_path, "r", encoding="utf-8") as file_obj:
            workflow = json.load(file_obj)

        payload = {
            "workflow": workflow,
            "input_image": image_path,
            "tasks": [
                {
                    "key": task.key,
                    "label": task.label,
                    "direction": task.direction,
                    "angle": task.angle,
                }
                for task in self.tasks
            ],
            "notes": [
                "必须使用 InstantID 或 IP-Adapter Face 锁定身份。",
                "不能只靠 prompt 控制 left/right。",
                "姿态节点必须显式区分 left/right/front。",
            ],
        }
        return payload

    def _run_fallback_pipeline(self, image: np.ndarray, processor=None) -> Dict[str, object]:
        logger.warning("强控制工作流未就绪，回退到旧版弱控制路线")
        generator = ImageGenerator(use_controlnet=strong_control_config.fallback_use_controlnet)
        images = generator.generate_all_rotations(image, processor)
        status = (
            "当前使用的是旧版弱控制回退路线，仅供预览。"
            "\n问题不会根治：仍可能换人，左右转也可能不准。"
            "\n要真正过工单，必须补齐 ComfyUI + InstantID/IP-Adapter Face 工作流。"
        )
        return {
            "mode": "fallback",
            "images": images,
            "outpaint_images": [],
            "status": status,
            "report": self.get_route_report(),
        }
