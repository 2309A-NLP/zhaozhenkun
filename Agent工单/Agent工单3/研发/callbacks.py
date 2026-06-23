# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：面部旋转 + 扩图回调函数模块
==============================================================================
本文件包含 Gradio 面部旋转 Tab 的核心回调函数：
  - detect_face: MediaPipe 人脸检测 + 姿态估计
  - generate_rotation: 用千问 Qwen-Image-Edit-Max 生成左/右/正三姿态面部 + 扩图

所有输出统一保存到 output/face_rotation/ 目录。

依赖：config, face_processor, utils, qwen_image_editor

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import cv2  # OpenCV 图像处理
import os  # 路径操作
import time  # 限流延时
import logging  # 日志

from config import OUTPUT_DIR, qwen_config  # 配置
from face_processor import FaceProcessor  # 人脸检测
from utils import save_image  # 图像保存

logger = logging.getLogger(__name__)  # 模块日志器

_face_proc = None  # 人脸处理器单例
_qwen_editor = None  # 千问编辑器单例


def _format_error(title: str, error: Exception) -> str:
    """统一格式化错误消息"""
    text = str(error).strip() or repr(error)
    logger.error(f"{title}: {text}")
    return f"❌ {title}: {text}"


def _init_face():
    """懒加载人脸处理器 (MediaPipe)"""
    global _face_proc
    if _face_proc is None:
        _face_proc = FaceProcessor()
        logger.info("人脸处理器已加载")


def _init_qwen():
    """懒加载千问图像编辑器"""
    global _qwen_editor
    if _qwen_editor is None:
        from qwen_image_editor import QwenImageEditor
        _qwen_editor = QwenImageEditor()
        logger.info("千问图像编辑器已加载")


def detect_face(image):
    """人脸检测回调：MediaPipe 检测 + 关键点提取 + 姿态估计"""
    if image is None:
        return "⚠️ 请先上传图像"
    try:
        _init_face()
        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)  # RGB→BGR
        bbox = _face_proc.detect_face(bgr)  # 人脸检测
        if bbox is None:
            return "❌ 未检测到人脸，请上传清晰的面部照片"
        landmarks = _face_proc.extract_landmarks(bgr)  # 关键点
        pose = _face_proc.estimate_pose(bgr)  # 姿态
        lines = [f"✅ 检测成功！人脸区域: {bbox[0]}x{bbox[1]}x{bbox[2]}x{bbox[3]}"]
        if landmarks is not None:
            lines.append(f"🎯 面部关键点: {len(landmarks)} 个")
        if pose is not None:
            lines.append(f"🔄 当前姿态: yaw={pose[0]:.1f}° pitch={pose[1]:.1f}° roll={pose[2]:.1f}°")
        lines.append("💡 检测通过，点击「生成旋转图像」开始 AI 处理")
        return "\n".join(lines)
    except Exception as e:
        return _format_error("人脸检测失败", e)


def generate_rotation(image):
    """生成三张旋转面部图像 + 扩图（使用千问 Qwen-Image-Edit-Max）

    流程：
    1. 人脸检测验证
    2. 千问 API 三次调用：左转 / 右转 / 端正
    3. 千问 API 三次调用：对三张旋转结果分别扩图
    4. 所有结果保存到 output/face_rotation/
    """
    if image is None:
        return None, None, None, None, None, None, "⚠️ 请先上传图像"

    try:
        _init_face()
        _init_qwen()

        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)  # RGB→BGR

        # 验证人脸存在
        if _face_proc.detect_face(bgr) is None:
            return None, None, None, None, None, None, "❌ 未检测到人脸，请重新上传"

        # 统一输出目录
        save_dir = os.path.join(OUTPUT_DIR, "face_rotation")
        os.makedirs(save_dir, exist_ok=True)
        save_image(bgr, os.path.join(save_dir, "original.png"))  # 保存原图

        # 三方向旋转任务定义
        rotation_tasks = [
            ("left", "保持人物身份完全不变，将头部转向左侧，面部朝向左方，"
                     "左侧脸轮廓清晰可见，自然光照，专业摄影"),
            ("right", "保持人物身份完全不变，将头部转向右侧，面部朝向右方，"
                      "右侧脸轮廓清晰可见，自然光照，专业摄影"),
            ("front", "保持人物身份完全不变，面部正对镜头，端正朝前，"
                      "对称构图，自然光照，专业摄影"),
        ]

        # 执行三次旋转
        results = []  # BGR 结果列表
        route_note = ""
        for key, prompt in rotation_tasks:
            logger.info(f"千问生成 {key} 旋转...")
            time.sleep(2)  # 限流控制
            result = _qwen_editor.edit(
                images=[bgr], prompt=prompt, n=1, size="1024*1024",
            )
            if result["success"] and result["images"]:
                results.append(result["images"][0])
                save_image(result["images"][0], os.path.join(save_dir, f"rotation_{key}.png"))
                logger.info(f"  ✅ {key} 已保存")
            else:
                logger.error(f"  ❌ {key} 失败: {result.get('error', '未知')}")
                results.append(bgr)  # 用原图兜底
                route_note += f" {key}生成失败;"

        # 扩图（对三张旋转结果分别扩图）
        outpaint_prompt = (
            "扩展图像画布，填充人物上半身和背景，保持人物身份完全不变，"
            "自然无缝扩展，专业摄影棚灯光，清晰锐利"
        )
        outpaint_results = []
        for i, (key, _) in enumerate(rotation_tasks):
            logger.info(f"千问扩图 {key}...")
            time.sleep(2)
            result = _qwen_editor.edit(
                images=[results[i]], prompt=outpaint_prompt,
                n=1, size="1280*1280",
            )
            if result["success"] and result["images"]:
                outpaint_results.append(result["images"][0])
                save_image(result["images"][0], os.path.join(save_dir, f"outpaint_{key}.png"))
                logger.info(f"  ✅ 扩图 {key} 已保存")
            else:
                logger.error(f"  ❌ 扩图 {key} 失败")
                outpaint_results.append(results[i])
                route_note += f" 扩图{key}失败;"

        # BGR → RGB 给 Gradio 显示
        rot_rgb = [cv2.cvtColor(r, cv2.COLOR_BGR2RGB) for r in results]
        out_rgb = [cv2.cvtColor(o, cv2.COLOR_BGR2RGB) for o in outpaint_results]

        status = (f"✅ 全部完成！\n📁 保存目录: {save_dir}\n"
                  f"🖼️ 旋转图像: 3 张 (左/右/正)\n🖼️ 扩图结果: 3 张\n"
                  f"🤖 模型: {qwen_config.model}")
        if route_note:
            status += f"\n⚠️ 提示: {route_note}"

        logger.info(status)
        return rot_rgb[0], rot_rgb[1], rot_rgb[2], out_rgb[0], out_rgb[1], out_rgb[2], status

    except Exception as e:
        return None, None, None, None, None, None, _format_error("生成失败", e)
