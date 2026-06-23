# -*- coding: utf-8 -*-
"""
ComfyUI 高级工作流模块 — 三姿态面部旋转执行。
execute_workflow_with_faces 通过 monkeypatch 注册到 ComfyUIClient。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
"""

import copy
import json
import logging
import os
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)

__all__ = ['_generate_pose_skeletons', 'execute_workflow_with_faces']


def _generate_pose_skeletons(source_img: np.ndarray) -> dict:
    """从原图生成 left/right/front 三种朝向的 OpenPose 骨架图（512x512）。

    优先用 controlnet_aux 提取真实骨架，失败时回退到简易骨架 + 翻转/模糊模拟朝向。
    """
    h, w = source_img.shape[:2]
    # 尝试提取真实骨架
    base = None
    try:
        from controlnet_aux import OpenposeDetector
        from PIL import Image
        detector = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
        pil_img = Image.fromarray(cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB)).resize((512, 512))
        pose_pil = detector(pil_img)  # 提取 OpenPose
        base = cv2.cvtColor(np.array(pose_pil), cv2.COLOR_RGB2BGR)
    except Exception:
        pass  # 提取失败则回退

    if base is None or base.max() < 10:  # 骨架过暗/为空 → 生成简易骨架
        base = np.zeros((512, 512, 3), dtype=np.uint8)
        pts = [(256, 120), (256, 200), (256, 200), (156, 280),  # nose→neck→L-shoulder
               (256, 200), (356, 280), (226, 110), (286, 110),  # neck→R-shoulder, eyes
               (216, 125), (296, 125)]  # ears
        for i in range(0, len(pts) - 1, 2):
            cv2.line(base, pts[i], pts[i + 1], (255, 255, 255), 2)  # 画骨架线
        for p in pts:
            cv2.circle(base, p, 4, (255, 255, 255), -1)  # 画关键点

    return {"left": cv2.flip(base, 1),         # 水平翻转 → 左朝向
            "right": base.copy(),               # 原图 → 右朝向
            "front": cv2.GaussianBlur(base, (5, 5), 0)}  # 模糊 → 正面（减少约束）


def execute_workflow_with_faces(self, source_image_path, output_dir,
                                workflow=None, workflow_path=None, timeout=None):
    """执行完整三姿态面部旋转工作流（左/右/正）。

    策略：
    1. 上传源图像作为 InstantID 身份参考
    2. 生成并上传三种朝向的 OpenPose 骨架图
    3. 对每个姿态使用不同 prompt + seed + 骨架图，依次提交执行
    4. 下载所有输出图像

    Returns: {"success": bool, "images": {"left": path, ...}, "prompt_ids": [...], "errors": [...]}
    """
    # 加载工作流
    if workflow is None and workflow_path:
        with open(workflow_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
    if workflow is None:
        raise ValueError("必须提供 workflow 或 workflow_path")

    # 加载并标准化源图像
    with open(source_image_path, "rb") as f:
        raw = np.frombuffer(f.read(), dtype=np.uint8)
    source_img = cv2.imdecode(raw, cv2.IMREAD_COLOR)  # BGR 解码
    if source_img is None:
        return {"success": False, "images": {}, "errors": ["无法加载源图像"]}
    source_img = cv2.resize(source_img, (512, 512))  # 标准化尺寸

    # 上传源图像（InstantID 身份参考）
    _, source_bytes = cv2.imencode(".png", source_img)
    upload_name = self.upload_image(source_bytes.tobytes(), filename="source_face.png")
    if upload_name is None:
        return {"success": False, "images": {}, "errors": ["上传源图像失败"]}

    # 生成骨架图
    try:
        from controlnet_aux import OpenposeDetector
        from PIL import Image
        detector = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
        pil = Image.fromarray(cv2.cvtColor(source_img, cv2.COLOR_BGR2RGB)).resize((512, 512))
        base_skel = cv2.cvtColor(np.array(detector(pil)), cv2.COLOR_RGB2BGR)
    except Exception:
        fallback = _generate_pose_skeletons(source_img)
        base_skel = fallback.get("front", fallback.get("right"))
        if base_skel is None:
            base_skel = np.zeros((512, 512, 3), dtype=np.uint8)

    skeletons = {"left": cv2.flip(base_skel, 1),       # 水平翻转
                 "right": base_skel.copy(),              # 原图
                 "front": cv2.GaussianBlur(base_skel, (3, 3), 0)}  # 轻微模糊

    # 上传骨架图
    skeleton_names = {}
    for key in ("left", "right", "front"):
        _, buf = cv2.imencode(".png", skeletons[key])
        name = self.upload_image(buf.tobytes(), filename=f"pose_skeleton_{key}.png")
        skeleton_names[key] = name
        logger.info(f"骨架图已上传: {key} -> {name}")

    # 三姿态配置
    poses = [
        {"key": "left", "label": "左转(-30°)",
         "prompt": ("exact same person, identical face and identity, same eyes, same nose, same mouth, "
                    "((head turned to the left:1.5)), ((facing left:1.5)), ((looking left:1.4)), "
                    "three-quarter left view, visible nose bridge rotation, natural cheek contour, "
                    "portrait of the same person turning head toward their left shoulder, "
                    "high quality, professional studio lighting, sharp focus, 8k"),
         "negative_prompt": ("front view, facing forward, looking at camera, turned right, "
                             "right profile, mirrored face, different person, face swap"),
         "seed": 100},
        {"key": "right", "label": "右转(+30°)",
         "prompt": ("exact same person, identical face and identity, same eyes, same nose, same mouth, "
                    "((head turned to the right:1.5)), ((facing right:1.5)), ((looking right:1.4)), "
                    "three-quarter right view, visible nose bridge rotation, natural cheek contour, "
                    "portrait of the same person turning head toward their right shoulder, "
                    "high quality, professional studio lighting, sharp focus, 8k"),
         "negative_prompt": ("front view, facing forward, looking at camera, turned left, "
                             "left profile, mirrored face, different person, face swap"),
         "seed": 200},
        {"key": "front", "label": "端正(0°)",
         "prompt": ("exact same person, identical face and identity, same eyes, same nose, same mouth, "
                    "((looking directly at camera:1.4)), ((front view:1.5)), ((facing forward:1.5)), "
                    "symmetrical face, straight on, centered composition, natural expression, "
                    "high quality, professional studio lighting, sharp focus, 8k"),
         "negative_prompt": ("turned left, turned right, profile view, side face, "
                             "different person, face swap"),
         "seed": 300},
    ]

    os.makedirs(output_dir, exist_ok=True)
    results = {"success": True, "images": {}, "prompt_ids": [], "errors": []}

    # 延迟导入辅助函数（避免顶层循环依赖）
    from comfyui_helpers import find_nodes_by_type, set_positive_prompt, set_negative_prompt, set_seed  # noqa: E402

    for pose in poses:
        logger.info(f"生成 {pose['label']}...")
        wf = copy.deepcopy(workflow)  # 深拷贝避免交叉污染

        # 修改工作流参数
        wf = set_positive_prompt(wf, pose["prompt"])
        wf = set_negative_prompt(wf, pose.get("negative_prompt", "bad"))
        wf = set_seed(wf, pose["seed"])

        # 更新 LoadImage 节点
        for nid, node in find_nodes_by_type(wf, "LoadImage"):
            cur = node.get("inputs", {}).get("image", "")
            if "skeleton" in str(cur):
                node["inputs"]["image"] = skeleton_names[pose["key"]]  # 骨架图
            elif "source" in str(cur) or "face" in str(cur).lower():
                node["inputs"]["image"] = upload_name  # 身份参考图
            # "pose" 相关节点保持原样

        # 保存调试工作流
        debug_path = os.path.join(output_dir, f"debug_workflow_{pose['key']}.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        logger.info(f"调试工作流已保存: {debug_path}")

        # 提交并等待
        history = self.execute_workflow(wf, timeout=timeout)
        if history is None:
            results["errors"].append(f"{pose['label']}: 执行超时或失败")
            results["success"] = False
            continue

        if history.get("status") and history["status"].get("completed") is False:
            results["errors"].append(f"{pose['label']}: {history.get('status', {})}")
            results["success"] = False
            continue

        # 下载输出
        saved = self.download_outputs(history, output_dir, prefix=pose["key"])
        if saved:
            results["images"][pose["key"]] = saved[0]
            logger.info(f"完成 {pose['label']}: {saved[0]}")
        else:
            results["errors"].append(f"{pose['label']}: 无输出图像")
            results["success"] = False

        time.sleep(1.0)  # 短暂冷却

    return results


# Monkeypatch 注册
from comfyui_client import ComfyUIClient  # noqa: E402
ComfyUIClient.execute_workflow_with_faces = execute_workflow_with_faces
