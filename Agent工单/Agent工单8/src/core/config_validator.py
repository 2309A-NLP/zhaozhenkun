"""
src/core/config_validator.py - 启动配置校验器
功能: 在系统启动前检查所有关键配置和环境依赖。
      发现问题时给出清晰的中文错误提示和修复建议。
      对应工单需求: 系统兼容性和稳定性
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import os
import sys
import shutil
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """单次检查结果。"""
    name: str           # 检查项名称
    passed: bool        # 是否通过
    level: str          # "error" | "warning" | "ok"
    message: str        # 详细信息
    fix_hint: str = ""  # 修复建议


class ConfigValidator:
    """启动配置校验器。在系统启动前进行全面检查。"""

    def __init__(self, config):
        """
        初始化校验器。
        参数:
            config: AppConfig实例
        """
        self.config = config
        self.results: list[CheckResult] = []

    def check_all(self) -> bool:
        """
        执行所有检查项。
        返回: True表示关键检查全部通过，False表示有阻塞性问题。
        """
        logger.info("=" * 50)
        logger.info("  系统环境检查")
        logger.info("=" * 50)

        checks = [
            self._check_python_version,
            self._check_gpu,
            self._check_api_key,
            self._check_ffmpeg,
            self._check_lipsync_model,
            self._check_llm_connectivity,
            self._check_output_dir,
        ]

        for check_fn in checks:
            result = check_fn()
            self.results.append(result)
            self._print_result(result)

        logger.info("=" * 50)

        # 统计
        errors = [r for r in self.results if r.level == "error"]
        warnings = [r for r in self.results if r.level == "warning"]

        if errors:
            logger.error(f"发现 {len(errors)} 个阻塞性问题:")
            for e in errors:
                logger.error(f"  ✗ {e.name}: {e.message}")
                if e.fix_hint:
                    logger.error(f"    修复: {e.fix_hint}")
        if warnings:
            logger.warning(f"发现 {len(warnings)} 个警告:")
            for w in warnings:
                logger.warning(f"  ⚠ {w.name}: {w.message}")

        if not errors:
            logger.info("✓ 所有关键检查通过，系统可以启动")
            return True
        return False

    def _print_result(self, r: CheckResult) -> None:
        """打印单条检查结果。"""
        icon = {"ok": "✓", "warning": "⚠", "error": "✗"}.get(r.level, "?")
        logger.info(f"  {icon} {r.name}: {r.message}")

    # ========== 各项检查 ==========

    def _check_python_version(self) -> CheckResult:
        """检查Python版本(需要≥3.10)。"""
        v = sys.version_info
        ok = v.major >= 3 and v.minor >= 10
        return CheckResult(
            name="Python版本",
            passed=ok,
            level="error" if not ok else "ok",
            message=f"Python {v.major}.{v.minor}.{v.micro} {'OK' if ok else '需要≥3.10'}",
            fix_hint="安装Python 3.10+: https://www.python.org/downloads/" if not ok else "",
        )

    def _check_gpu(self) -> CheckResult:
        """检查GPU可用性。"""
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                return CheckResult(
                    name="GPU",
                    passed=True,
                    level="ok",
                    message=f"{name} ({vram:.1f}GB) OK",
                )
            else:
                return CheckResult(
                    name="GPU",
                    passed=True,  # 不算错误，CPU也能跑（慢）
                    level="warning",
                    message="CUDA不可用，将使用CPU(推理很慢)",
                )
        except ImportError:
            return CheckResult(
                name="PyTorch",
                passed=False,
                level="error",
                message="PyTorch未安装",
                fix_hint="pip install torch>=2.0.0",
            )

    def _check_api_key(self) -> CheckResult:
        """检查LLM API Key是否设置。"""
        key = self.config.llm.api_key
        provider = self.config.llm.provider

        if provider == "ollama":
            return CheckResult(
                name="API Key",
                passed=True,
                level="ok",
                message="Ollama本地模式，无需API Key",
            )

        if not key:
            return CheckResult(
                name="API Key",
                passed=False,
                level="error",
                message=f"未设置 {provider.upper()}_API_KEY 环境变量",
                fix_hint=f"执行: export DEEPSEEK_API_KEY=sk-你的key",
            )

        # 简单检查格式
        if provider == "deepseek" and not key.startswith("sk-"):
            return CheckResult(
                name="API Key",
                passed=True,
                level="warning",
                message="API Key格式可能不正确",
            )

        return CheckResult(
            name="API Key",
            passed=True,
            level="ok",
            message=f"已设置 ({provider})",
        )

    def _check_ffmpeg(self) -> CheckResult:
        """检查FFmpeg是否可用。"""
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return CheckResult(
                name="FFmpeg",
                passed=True,
                level="ok",
                message=f"可用: {ffmpeg_path}",
            )
        return CheckResult(
            name="FFmpeg",
            passed=False,
            level="warning",
            message="FFmpeg未找到，TTS/RTMP功能受限",
            fix_hint="apt install ffmpeg (Ubuntu) 或 brew install ffmpeg (macOS)",
        )

    def _check_lipsync_model(self) -> CheckResult:
        """检查唇形同步模型权重。"""
        model = self.config.lipsync.model
        checkpoint = self.config.lipsync.checkpoint

        # SadTalker — 检查已有模型路径(使用自动检测)
        if model == "sadtalker":
            from src.lipsync.sadtalker_engine import _detect_sadtalker_root
            sadtalker_root = getattr(self.config.lipsync, 'sadtalker_root', '')
            root = _detect_sadtalker_root(sadtalker_root)
            sadtalker_ckpt = os.path.join(root, "checkpoints", "SadTalker_V0.0.2_512.safetensors")
            if os.path.exists(sadtalker_ckpt):
                size_mb = os.path.getsize(sadtalker_ckpt) / (1024*1024)
                return CheckResult(name=f"唇形同步(SadTalker)", passed=True,
                                   level="ok", message=f"已有 {size_mb:.0f}MB ({root})")
            return CheckResult(name=f"唇形同步(SadTalker)", passed=False,
                               level="warning", message=f"SadTalker权重缺失: {root}",
                               fix_hint=f"检查 {root}/checkpoints/ 目录")

        if os.path.exists(checkpoint):
            size_mb = os.path.getsize(checkpoint) / (1024 * 1024)
            return CheckResult(name=f"唇形同步模型({model})", passed=True,
                               level="ok", message=f"权重已就绪 ({size_mb:.0f}MB)")
        return CheckResult(name=f"唇形同步模型({model})", passed=False,
                           level="warning", message=f"权重缺失: {checkpoint}，将使用占位模式",
                           fix_hint="运行: python scripts/download_models.py")

    def _check_llm_connectivity(self) -> CheckResult:
        """检查LLM API连通性(可选，不阻塞启动)。"""
        api_base = self.config.llm.api_base
        provider = self.config.llm.provider

        if provider == "ollama":
            return CheckResult(
                name="LLM连接",
                passed=True,
                level="ok",
                message="Ollama本地服务(假设就绪)",
            )

        # 尝试简单HTTP检查
        try:
            import urllib.request
            req = urllib.request.Request(api_base + "/models", method="GET")
            req.add_header("User-Agent", "DigitalHuman/1.0")
            urllib.request.urlopen(req, timeout=5)
            return CheckResult(
                name="LLM连接",
                passed=True,
                level="ok",
                message=f"{api_base} 可达",
            )
        except Exception:
            return CheckResult(
                name="LLM连接",
                passed=True,  # 不阻塞，可能是网络限制
                level="warning",
                message=f"{api_base} 无法连接(启动后可重试)",
            )

    def _check_output_dir(self) -> CheckResult:
        """检查输出目录可写性。"""
        output_dir = "output"
        try:
            os.makedirs(output_dir, exist_ok=True)
            test_file = os.path.join(output_dir, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return CheckResult(
                name="输出目录",
                passed=True,
                level="ok",
                message=f"'{output_dir}/' 可写",
            )
        except (PermissionError, OSError):
            return CheckResult(
                name="输出目录",
                passed=False,
                level="error",
                message=f"'{output_dir}/' 不可写",
                fix_hint=f"chmod 755 {output_dir}",
            )


def validate_config(config) -> bool:
    """
    便捷函数: 校验配置并返回是否可以启动。
    参数:
        config: AppConfig实例
    返回:
        True表示可以启动，False表示有阻塞性错误
    """
    validator = ConfigValidator(config)
    return validator.check_all()
