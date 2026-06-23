# -*- coding: utf-8 -*-
"""
ComfyUI 工作流参数修改辅助模块 — 节点查找、prompt/seed/文件修改、格式转换、底模对齐。
_workflow_to_api_format 通过 monkeypatch 注册为 ComfyUIClient 静态方法。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
"""

import copy
import json
import logging
import os
from typing import Any, Dict, List

from config import strong_control_config

logger = logging.getLogger(__name__)

__all__ = ['find_nodes_by_type', 'set_positive_prompt', 'set_negative_prompt',
           'set_seed', 'set_load_image_filename', 'set_checkpoint',
           'set_save_image_prefix', 'align_instantid_workflow_family',
           'get_node_ids_by_type', '_workflow_to_api_format']


# ================================================================
# 节点查找
# ================================================================

def find_nodes_by_type(workflow: Dict[str, Any], node_type: str) -> List[tuple]:
    """在 API 格式工作流中查找指定 class_type 的所有节点。Returns [(node_id, node_data), ...]"""
    result = []
    for node_id, node_data in workflow.items():
        if isinstance(node_data, dict) and node_data.get("class_type") == node_type:
            result.append((node_id, node_data))
    return result


# ================================================================
# Prompt 修改
# ================================================================

def set_positive_prompt(workflow: Dict[str, Any], prompt_text: str) -> Dict[str, Any]:
    """修改第一个 CLIPTextEncode 节点的正向 prompt（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    clip_nodes = find_nodes_by_type(wf, "CLIPTextEncode")
    if not clip_nodes:
        logger.warning("工作流中无 CLIPTextEncode 节点")
        return wf
    clip_nodes[0][1].setdefault("inputs", {})["text"] = prompt_text  # 第一个=正向
    return wf


def set_negative_prompt(workflow: Dict[str, Any], prompt_text: str) -> Dict[str, Any]:
    """修改第二个 CLIPTextEncode 节点的负向 prompt（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    clip_nodes = find_nodes_by_type(wf, "CLIPTextEncode")
    if len(clip_nodes) < 2:
        logger.warning("工作流中少于 2 个 CLIPTextEncode 节点")
        return wf
    clip_nodes[1][1].setdefault("inputs", {})["text"] = prompt_text  # 第二个=负向
    return wf


# ================================================================
# 采样参数修改
# ================================================================

def set_seed(workflow: Dict[str, Any], seed: int) -> Dict[str, Any]:
    """修改第一个 KSampler 节点的种子值（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    ksamplers = find_nodes_by_type(wf, "KSampler")
    if not ksamplers:
        logger.warning("工作流中无 KSampler 节点")
        return wf
    ksamplers[0][1].setdefault("inputs", {})["seed"] = seed
    return wf


# ================================================================
# 输入文件修改
# ================================================================

def set_load_image_filename(workflow: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """修改所有 LoadImage 节点的图像文件名（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    for _, node in find_nodes_by_type(wf, "LoadImage"):
        node.setdefault("inputs", {})["image"] = filename
    return wf


def set_checkpoint(workflow: Dict[str, Any], checkpoint_name: str) -> Dict[str, Any]:
    """修改所有 CheckpointLoaderSimple 节点的 ckpt_name（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    for _, node in find_nodes_by_type(wf, "CheckpointLoaderSimple"):
        node.setdefault("inputs", {})["ckpt_name"] = checkpoint_name
    return wf


def set_save_image_prefix(workflow: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """修改所有 SaveImage 节点的输出前缀（深拷贝）。"""
    wf = copy.deepcopy(workflow)
    for _, node in find_nodes_by_type(wf, "SaveImage"):
        node.setdefault("inputs", {})["filename_prefix"] = prefix
    return wf


# ================================================================
# 节点 ID 映射
# ================================================================

def get_node_ids_by_type(workflow: Dict[str, Any]) -> Dict[str, List[str]]:
    """返回 {class_type: [node_id, ...]} 映射。"""
    mapping: Dict[str, List[str]] = {}
    for node_id, node_data in workflow.items():
        if isinstance(node_data, dict) and "class_type" in node_data:
            mapping.setdefault(node_data["class_type"], []).append(node_id)
    return mapping


# ================================================================
# 工作流格式转换
# ================================================================

def _workflow_to_api_format(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """将 nodes 数组格式工作流转换为 API 对象格式。

    nodes 格式: {"nodes": [{"id":1,"type":"...","inputs":[...]}], "links":[[...],...]}
    API 格式:   {"1": {"class_type":"...","inputs":{"name":[from_node,slot]}}}
    """
    if "nodes" not in workflow:  # 已是 API 格式
        return workflow

    # link_id → (from_node, from_slot) 映射
    link_map = {}
    for link in workflow.get("links", []):
        link_map[link[0]] = (link[1], link[2])

    api = {}
    for node in workflow["nodes"]:
        node_id = str(node["id"])  # 转为字符串键
        node_inputs = {}
        for inp in node.get("inputs", []):
            inp_link = inp.get("link")
            if inp_link is not None and inp_link in link_map:
                from_node, from_slot = link_map[inp_link]
                node_inputs[inp["name"]] = [str(from_node), from_slot]  # 连接引用
            else:
                node_inputs[inp["name"]] = None  # widget 控制
        api[node_id] = {"class_type": node["type"], "inputs": node_inputs}
        widgets = node.get("widgets_values", [])
        if widgets:
            api[node_id]["_meta"] = {"widget_values": widgets}  # 附加元数据
    return api


# ================================================================
# InstantID 工作流对齐
# ================================================================

def align_instantid_workflow_family(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """按 strong_control_config 强制对齐 checkpoint 和 ControlNet 模型。

    根据 checkpoint_family (sd15/sdxl) 自动选择正确的模型文件名。
    """
    wf = copy.deepcopy(workflow)
    checkpoint_name = getattr(strong_control_config, "checkpoint_name", "")
    checkpoint_family = str(getattr(strong_control_config, "checkpoint_family", "")).lower()
    instantid_cn_name = getattr(strong_control_config, "instantid_controlnet_name", "")

    if checkpoint_name:
        wf = set_checkpoint(wf, checkpoint_name)  # 设置底模

    # 根据底模家族确定合法 ControlNet 文件名
    if checkpoint_family == "sd15":
        valid = ["ControlNetModel/diffusion_pytorch_model.safetensors",
                 "instantid/diffusion_pytorch_model.safetensors"]
        if instantid_cn_name not in valid:
            instantid_cn_name = "ControlNetModel/diffusion_pytorch_model.safetensors"
    elif checkpoint_family == "sdxl":
        valid = ["instantid/diffusion_pytorch_model.safetensors"]
        if instantid_cn_name not in valid:
            instantid_cn_name = "instantid/diffusion_pytorch_model.safetensors"

    # 更新 ControlNetLoader 节点
    if instantid_cn_name:
        for _, node in find_nodes_by_type(wf, "ControlNetLoader"):
            current = str(node.setdefault("inputs", {}).get("control_net_name", "")).lower()
            if "instantid" in current or "controlnetmodel" in current or "diffusion_pytorch_model" in current:
                node["inputs"]["control_net_name"] = instantid_cn_name
    return wf


# ================================================================
# Monkeypatch 注册
# ================================================================
from comfyui_client import ComfyUIClient  # noqa: E402
ComfyUIClient._workflow_to_api_format = staticmethod(_workflow_to_api_format)


# ================================================================
# 测试入口
# ================================================================
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="ComfyUI API 客户端测试")
    parser.add_argument("--url", default="http://127.0.0.1:8188", help="ComfyUI 服务器地址")
    parser.add_argument("--input", "-i", required=True, help="源人脸图像路径")
    parser.add_argument("--workflow", "-w", required=True, help="工作流 JSON 文件路径")
    parser.add_argument("--output", "-o", default="output/comfyui", help="输出目录")
    parser.add_argument("--check", action="store_true", help="仅检查服务器连接")
    args = parser.parse_args()

    client = ComfyUIClient(base_url=args.url)  # 创建客户端

    if args.check:
        if client.check_health():
            logger.info("ComfyUI 服务器在线")
        else:
            logger.error("ComfyUI 服务器未响应")
        exit(0)

    # 等待服务器就绪
    if not client.wait_for_server(timeout=60):
        logger.error("ComfyUI 未能在 60s 内启动")
        exit(1)

    # 执行三姿态工作流
    result = client.execute_workflow_with_faces(source_image_path=args.input,
                                                output_dir=args.output,
                                                workflow_path=args.workflow)

    if result["success"]:
        logger.info("全部生成完成！")
        for pose_key, path in result["images"].items():
            logger.info(f"  {pose_key}: {path}")
    else:
        logger.error(f"生成失败: {result['errors']}")
        exit(1)
