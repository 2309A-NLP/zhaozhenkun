"""文件功能：封装 Ultralight-Digital-Human 的真实预处理、训练、特征提取与推理命令。"""
from __future__ import annotations  # 启用延后类型注解支持。

import json  # 写入结构化结果文件。
import shutil  # 检查外部命令和复制素材文件。
import subprocess  # 调用真实 Ultralight 训练与推理命令。
from pathlib import Path  # 处理路径对象。
from typing import Any  # 描述通用数据结构。

from 设计.architecture import AppSettings  # 导入应用配置类型。


class UltralightAdapter:  # 定义 Ultralight 真实适配层。
    def __init__(self, settings: AppSettings) -> None:  # 初始化适配器。
        self.settings = settings  # 保存全局配置。

    def _job_dir(self, job_prefix: str, job_id: str) -> Path:  # 计算任务输出目录。
        path = self.settings.output_dir / job_prefix / job_id  # 拼接任务目录路径。
        path.mkdir(parents=True, exist_ok=True)  # 确保目录存在。
        return path  # 返回任务目录路径。

    def _require_ultralight_root(self) -> Path:  # 获取并校验 Ultralight 根目录。
        root = self.settings.ultralight_root  # 读取 Ultralight 根目录配置。
        if root is None or not root.exists():  # 如果根目录未配置或不存在。
            raise ValueError("未配置可用的 ULTRALIGHT_ROOT，无法执行真实 Ultralight 命令。")  # 抛出明确异常。
        return root  # 返回有效根目录。

    def _require_ffmpeg(self) -> None:  # 检查 ffmpeg 是否可用。
        if shutil.which("ffmpeg") is None:  # 如果系统路径中找不到 ffmpeg。
            raise ValueError("系统未安装 ffmpeg，无法执行 Ultralight 预处理或音视频合成。")  # 抛出明确异常。

    def _python_cmd(self) -> list[str]:  # 获取执行 Ultralight 脚本的 Python 命令前缀。
        python_cmd = self.settings.ultralight_python or "py -3"  # 读取配置中的 Python 命令。
        return python_cmd.split()  # 按空格切分为命令列表。

    def _run(self, cmd: list[str], cwd: Path, log_path: Path) -> None:  # 执行外部命令并把输出写入日志。
        result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="ignore")  # 执行外部命令并捕获输出。
        log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")  # 保存命令执行日志。
        if result.returncode != 0:  # 如果命令执行失败。
            raise ValueError(f"Ultralight 命令执行失败：{' '.join(cmd)}")  # 抛出统一业务异常。

    def _pick_training_video(self, assets: list[dict[str, Any]]) -> Path:  # 选择训练所需的视频素材。
        for asset in assets:  # 遍历参与训练的素材记录。
            path_text = str(asset.get("file_path", ""))  # 读取素材文件路径。
            if not path_text:  # 如果素材没有本地路径。
                continue  # 继续检查下一条素材。
            candidate = Path(path_text)  # 构造素材路径对象。
            if candidate.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"} and candidate.exists():  # 如果是存在的视频素材。
                return candidate  # 返回首个可用视频文件路径。
        raise ValueError("真实 Ultralight 训练需要至少一个存在的视频素材文件。")  # 没有视频素材时抛出异常。

    def _pick_avatar_image(self, persona: dict[str, Any], assets_by_id: dict[str, dict[str, Any]]) -> str:  # 选择可选头像图片路径。
        avatar_id = str(persona.get("avatar_image_asset_id", ""))  # 读取画像绑定的头像素材主键。
        if avatar_id and avatar_id in assets_by_id:  # 如果存在绑定头像素材。
            candidate = Path(str(assets_by_id[avatar_id].get("file_path", "")))  # 构造头像路径对象。
            if candidate.exists():  # 如果头像文件存在。
                return str(candidate)  # 返回头像图片路径。
        for asset in assets_by_id.values():  # 遍历全部素材记录。
            path_text = str(asset.get("file_path", ""))  # 读取素材路径。
            if path_text and Path(path_text).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:  # 如果是图片素材。
                candidate = Path(path_text)  # 构造图片路径对象。
                if candidate.exists():  # 如果图片文件存在。
                    return str(candidate)  # 返回首个可用图片路径。
        return ""  # 没有图片素材时返回空字符串。

    def _check(self, name: str, ok: bool, detail: str, value: str = "") -> dict[str, object]:  # 构造统一检查结果。
        return {"name": name, "ok": ok, "detail": detail, "value": value}  # 返回结构化检查信息。

    def _check_script(self, root: Path | None, relative_path: str) -> dict[str, object]:  # 检查 Ultralight 关键脚本是否存在。
        if root is None:  # 如果根目录不可用。
            return self._check(relative_path, False, "未配置有效的 ULTRALIGHT_ROOT。")  # 返回失败结果。
        target = root / relative_path  # 计算脚本实际路径。
        return self._check(relative_path, target.exists(), "脚本已就绪。" if target.exists() else "缺少关键脚本。", str(target))  # 返回脚本检查结果。

    def _python_executable_check(self) -> dict[str, object]:  # 检查 Ultralight Python 命令是否可执行。
        command_parts = self._python_cmd()  # 读取 Python 启动命令。
        executable = command_parts[0] if command_parts else ""  # 获取命令名。
        exists = bool(executable and (shutil.which(executable) or Path(executable).exists()))  # 判断命令是否存在。
        return self._check("ultralight_python", exists, "Ultralight Python 命令可用。" if exists else "ULTRALIGHT_PYTHON 不可执行。", executable)  # 返回检查结果。

    def _tts_source_check(self) -> dict[str, object]:  # 检查驱动音频来源是否可用。
        if self.settings.external_tts_command:  # 如果配置了外部 TTS 命令。
            command_parts = self.settings.external_tts_command.split()  # 按当前执行规则拆分命令。
            executable = command_parts[0] if command_parts else ""  # 获取可执行程序名。
            exists = bool(executable and (shutil.which(executable) or Path(executable).exists()))  # 判断命令是否存在。
            return self._check("tts_source", exists, "外部 TTS 命令可用。" if exists else "外部 TTS 命令不存在或不可执行。", executable)  # 返回命令检查结果。
        if self.settings.ultralight_audio_wav:  # 如果配置了固定驱动音频。
            audio_path = Path(self.settings.ultralight_audio_wav)  # 构造固定音频路径对象。
            return self._check("tts_source", audio_path.exists(), "固定驱动音频可用。" if audio_path.exists() else "固定驱动音频文件不存在。", str(audio_path))  # 返回音频检查结果。
        return self._check("tts_source", False, "未配置 EXTERNAL_TTS_COMMAND 或 ULTRALIGHT_AUDIO_WAV。")  # 返回默认缺失结果。

    def describe_readiness(self) -> dict[str, object]:  # 汇总当前真实链路的全局就绪情况。
        root = self.settings.ultralight_root if self.settings.ultralight_root and self.settings.ultralight_root.exists() else None  # 获取有效根目录。
        ffmpeg_path = shutil.which("ffmpeg") or ""  # 读取系统中的 ffmpeg 路径。
        feature_script = "data_utils/hubert.py" if self.settings.ultralight_asr == "hubert" else "data_utils/wenet_infer.py"  # 计算当前特征脚本路径。
        checks = [  # 汇总当前全局检查项。
            self._check("mock_mode", self.settings.use_mock_response, "当前运行在 mock 模式。" if self.settings.use_mock_response else "当前运行在真实模式。", "mock" if self.settings.use_mock_response else "real"),  # 记录当前模式。
            self._check("deepseek", self.settings.has_deepseek_credentials, "DeepSeek 凭证已配置。" if self.settings.has_deepseek_credentials else "未配置完整的 DeepSeek 凭证。", self.settings.deepseek_model),  # 检查文本模型凭证。
            self._check("qwen", self.settings.has_qwen_credentials, "Qwen 凭证已配置。" if self.settings.has_qwen_credentials else "未配置完整的 Qwen 凭证。", self.settings.qwen_model),  # 检查多模态模型凭证。
            self._check("ultralight_root", root is not None, "Ultralight 根目录可用。" if root is not None else "未配置可用的 ULTRALIGHT_ROOT。", str(self.settings.ultralight_root or "")),  # 检查 Ultralight 根目录。
            self._python_executable_check(),  # 检查 Ultralight Python 命令。
            self._check("ffmpeg", bool(ffmpeg_path), "ffmpeg 已安装。" if ffmpeg_path else "系统中未找到 ffmpeg。", ffmpeg_path),  # 检查 ffmpeg。
            self._check_script(root, "data_utils/process.py"),  # 检查预处理脚本。
            self._check_script(root, "train.py"),  # 检查训练脚本。
            self._check_script(root, "inference.py"),  # 检查推理脚本。
            self._check_script(root, feature_script),  # 检查音频特征脚本。
            self._tts_source_check(),  # 检查驱动音频来源。
        ]  # 完成全局检查项构造。
        required_names = {"deepseek", "ultralight_root", "ultralight_python", "ffmpeg", "data_utils/process.py", "train.py", "inference.py", feature_script, "tts_source"}  # 定义完整链路所需检查项。
        missing_items = [str(item["detail"]) for item in checks if item["name"] in required_names and not item["ok"]]  # 汇总真实链路缺失项。
        return {  # 返回结构化就绪信息。
            "effective_mode": "mock" if self.settings.use_mock_response else "real",  # 返回当前生效模式。
            "mock_mode": self.settings.use_mock_response,  # 返回 mock 标记。
            "real_pipeline_ready": not missing_items,  # 返回真实管线是否可执行。
            "checks": checks,  # 返回全部检查项。
            "missing_items": missing_items,  # 返回缺失项列表。
        }  # 结束就绪信息构造。

    def preflight_training(self, persona: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, object]:  # 预检训练任务执行条件。
        readiness = self.describe_readiness()  # 获取全局就绪状态。
        selected_video = ""  # 初始化训练视频路径。
        video_ok = False  # 初始化训练视频检查结果。
        video_detail = ""  # 初始化训练视频说明。
        try:  # 尝试解析训练视频素材。
            selected_video = str(self._pick_training_video(assets))  # 选取首个视频素材。
            video_ok = True  # 标记检查通过。
            video_detail = "已找到训练视频素材。"  # 保存成功说明。
        except ValueError as exc:  # 如果没有可用视频素材。
            video_detail = str(exc)  # 记录失败原因。
        checks = [  # 构造训练预检项。
            self._check("persona", bool(persona.get("persona_id")), "数字人记录可用。" if persona.get("persona_id") else "未找到有效的数字人记录。", str(persona.get("persona_id", ""))),  # 检查数字人。
            self._check("training_video", video_ok, video_detail, selected_video),  # 检查训练视频素材。
        ]  # 完成训练预检项构造。
        global_required = {"ultralight_root", "ultralight_python", "ffmpeg", "data_utils/process.py", "train.py"}  # 定义训练需要的全局检查项。
        missing_items = [str(item["detail"]) for item in readiness["checks"] if item["name"] in global_required and not item["ok"]] + [str(item["detail"]) for item in checks if not item["ok"]]  # 汇总训练缺失项。
        ready_for_real_run = not missing_items  # 判断真实训练是否可执行。
        return {  # 返回训练预检结果。
            "persona_id": str(persona.get("persona_id", "")),  # 返回数字人主键。
            "asset_count": len(assets),  # 返回待训练素材数量。
            "selected_video": selected_video,  # 返回选中的训练视频。
            "ready_for_current_mode": True if self.settings.use_mock_response else ready_for_real_run,  # 返回当前模式下是否允许继续。
            "ready_for_real_run": ready_for_real_run,  # 返回真实训练是否可执行。
            "checks": checks,  # 返回训练预检项。
            "global_readiness": readiness,  # 返回全局就绪状态。
            "missing_items": missing_items,  # 返回缺失项列表。
        }  # 结束训练预检结果构造。

    def preflight_avatar(self, persona: dict[str, Any], assets: list[dict[str, Any]]) -> dict[str, object]:  # 预检数字人推理执行条件。
        readiness = self.describe_readiness()  # 获取全局就绪状态。
        dataset_dir_text = str(persona.get("ultralight_dataset_dir", "")).strip()  # 读取训练数据目录文本。
        checkpoint_text = str(persona.get("ultralight_checkpoint_path", "")).strip()  # 读取训练权重路径文本。
        dataset_dir = Path(dataset_dir_text) if dataset_dir_text else None  # 构造训练数据目录对象。
        checkpoint_path = Path(checkpoint_text) if checkpoint_text else None  # 构造训练权重路径对象。
        avatar_image = self._pick_avatar_image(persona, {str(item.get("asset_id", "")): item for item in assets})  # 解析头像图片路径。
        checks = [  # 构造数字人推理预检项。
            self._check("persona", bool(persona.get("persona_id")), "数字人记录可用。" if persona.get("persona_id") else "未找到有效的数字人记录。", str(persona.get("persona_id", ""))),  # 检查数字人。
            self._check("dataset_dir", dataset_dir is not None and dataset_dir.exists(), "训练数据目录可用。" if dataset_dir is not None and dataset_dir.exists() else "数字人尚未绑定有效的训练数据目录。", str(dataset_dir or "")),  # 检查训练数据目录。
            self._check("checkpoint", checkpoint_path is not None and checkpoint_path.exists(), "训练权重可用。" if checkpoint_path is not None and checkpoint_path.exists() else "数字人尚未绑定有效的训练权重。", str(checkpoint_path or "")),  # 检查训练权重。
            self._check("avatar_image", bool(avatar_image), "已找到可用头像图片。" if avatar_image else "未绑定头像图片，将使用默认图片选择逻辑。", avatar_image),  # 检查头像素材。
        ]  # 完成数字人推理预检项构造。
        feature_script = "data_utils/hubert.py" if self.settings.ultralight_asr == "hubert" else "data_utils/wenet_infer.py"  # 计算当前特征脚本路径。
        global_required = {"ultralight_root", "ultralight_python", "ffmpeg", "inference.py", feature_script, "tts_source"}  # 定义推理需要的全局检查项。
        missing_items = [str(item["detail"]) for item in readiness["checks"] if item["name"] in global_required and not item["ok"]] + [str(item["detail"]) for item in checks if item["name"] in {"persona", "dataset_dir", "checkpoint"} and not item["ok"]]  # 汇总推理缺失项。
        ready_for_real_run = not missing_items  # 判断真实推理是否可执行。
        return {  # 返回数字人推理预检结果。
            "persona_id": str(persona.get("persona_id", "")),  # 返回数字人主键。
            "dataset_dir": str(dataset_dir or ""),  # 返回训练数据目录。
            "checkpoint": str(checkpoint_path or ""),  # 返回训练权重路径。
            "avatar_image": avatar_image,  # 返回头像图片路径。
            "ready_for_current_mode": True if self.settings.use_mock_response else ready_for_real_run,  # 返回当前模式下是否允许继续。
            "ready_for_real_run": ready_for_real_run,  # 返回真实推理是否可执行。
            "checks": checks,  # 返回推理预检项。
            "global_readiness": readiness,  # 返回全局就绪状态。
            "missing_items": missing_items,  # 返回阻塞执行的缺失项。
        }  # 结束数字人推理预检结果构造。

    def _validate_training_manifest(self, manifest_path: Path) -> dict[str, Any]:  # 校验真实训练产物清单。
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))  # 读取训练产物清单。
        dataset_dir_text = str(manifest.get("dataset_dir", "")).strip()  # 读取数据目录路径文本。
        checkpoint_text = str(manifest.get("checkpoint", "")).strip()  # 读取权重路径文本。
        dataset_dir = Path(dataset_dir_text) if dataset_dir_text else None  # 构造数据目录对象。
        checkpoint_path = Path(checkpoint_text) if checkpoint_text else None  # 构造权重路径对象。
        if dataset_dir is None or not dataset_dir.exists():  # 如果训练数据目录不可用。
            raise ValueError("真实 Ultralight 训练完成后未找到有效的数据目录。")  # 抛出明确异常。
        if checkpoint_path is None or not checkpoint_path.exists():  # 如果训练权重不可用。
            raise ValueError("真实 Ultralight 训练完成后未找到有效的权重文件。")  # 抛出明确异常。
        return manifest  # 返回通过校验的训练清单。

    def _mock_training_artifacts(self, persona: dict[str, Any], assets: list[dict[str, Any]], job_id: str) -> str:  # 在模拟模式下生成训练结果。
        job_dir = self._job_dir("training", job_id)  # 获取训练任务输出目录。
        dataset_dir = job_dir / "dataset"  # 约定模拟数据目录。
        checkpoint_dir = job_dir / "checkpoints"  # 约定模拟权重目录。
        dataset_dir.mkdir(parents=True, exist_ok=True)  # 确保模拟数据目录存在。
        checkpoint_dir.mkdir(parents=True, exist_ok=True)  # 确保模拟权重目录存在。
        checkpoint_path = checkpoint_dir / "last.pth"  # 计算模拟权重路径。
        checkpoint_path.write_text("mock checkpoint", encoding="utf-8")  # 生成模拟权重文件。
        manifest = {  # 构造模拟训练结果清单。
            "profile": self.settings.ultralight_profile,  # 记录当前配置名。
            "persona": persona,  # 记录数字人画像。
            "dataset_dir": str(dataset_dir),  # 记录模拟数据目录。
            "checkpoint": str(checkpoint_path),  # 记录模拟权重路径。
            "assets": assets,  # 记录参与训练的素材。
            "mode": "mock",  # 标记当前为模拟模式。
        }  # 完成结果清单构造。
        manifest_path = job_dir / "training_manifest.json"  # 计算清单输出路径。
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")  # 写入模拟训练清单。
        return str(manifest_path)  # 返回模拟训练清单路径。

    def prepare_training_artifacts(self, persona: dict[str, Any], assets: list[dict[str, Any]], job_id: str) -> str:  # 执行真实 Ultralight 预处理与训练。
        if self.settings.use_mock_response:  # 如果当前处于模拟模式。
            return self._mock_training_artifacts(persona, assets, job_id)  # 直接返回模拟训练产物。
        root = self._require_ultralight_root()  # 获取有效的 Ultralight 根目录。
        self._require_ffmpeg()  # 校验 ffmpeg 命令可用。
        video_path = self._pick_training_video(assets)  # 选择训练视频素材。
        job_dir = self._job_dir("training", job_id)  # 获取训练任务输出目录。
        dataset_dir = job_dir / "dataset"  # 约定训练数据目录。
        dataset_dir.mkdir(parents=True, exist_ok=True)  # 确保数据目录存在。
        work_video = dataset_dir / video_path.name  # 计算复制后的训练视频路径。
        if work_video.resolve() != video_path.resolve():  # 如果源视频不在目标目录内。
            shutil.copy2(video_path, work_video)  # 复制视频到训练数据目录。
        preprocess_log = job_dir / "process.log"  # 计算预处理日志路径。
        train_log = job_dir / "train.log"  # 计算训练日志路径。
        checkpoint_dir = job_dir / "checkpoints"  # 计算训练权重目录。
        checkpoint_dir.mkdir(parents=True, exist_ok=True)  # 确保权重目录存在。
        process_cmd = self._python_cmd() + [str(root / "data_utils" / "process.py"), str(work_video), "--asr", self.settings.ultralight_asr]  # 构造预处理命令。
        self._run(process_cmd, root, preprocess_log)  # 执行预处理命令。
        train_cmd = self._python_cmd() + [str(root / "train.py"), "--dataset_dir", str(dataset_dir), "--save_dir", str(checkpoint_dir), "--asr", self.settings.ultralight_asr, "--epochs", str(self.settings.ultralight_train_epochs), "--batchsize", str(self.settings.ultralight_batch_size)]  # 构造训练命令。
        self._run(train_cmd, root, train_log)  # 执行训练命令。
        trained_checkpoint = checkpoint_dir / "last.pth"  # 约定最终权重路径。
        manifest = {  # 构造训练结果清单。
            "profile": self.settings.ultralight_profile,  # 记录当前配置名。
            "persona": persona,  # 记录数字人画像。
            "dataset_dir": str(dataset_dir),  # 记录训练数据目录。
            "checkpoint": str(trained_checkpoint),  # 记录训练输出权重路径。
            "assets": assets,  # 记录参与训练的素材。
            "mode": "real",  # 标记当前为真实模式。
        }  # 完成训练结果清单构造。
        manifest_path = job_dir / "training_manifest.json"  # 计算清单输出路径。
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")  # 写入训练清单文件。
        self._validate_training_manifest(manifest_path)  # 校验真实训练产物是否齐全。
        return str(manifest_path)  # 返回训练清单路径。

    def _validate_avatar_result(self, result_path: Path) -> dict[str, Any]:  # 校验真实数字人推理产物。
        payload = json.loads(result_path.read_text(encoding="utf-8"))  # 读取推理结果清单。
        audio_feature_text = str(payload.get("audio_feature", "")).strip()  # 读取音频特征路径文本。
        video_path_text = str(payload.get("video_path", "")).strip()  # 读取视频路径文本。
        audio_feature = Path(audio_feature_text) if audio_feature_text else None  # 构造音频特征路径对象。
        video_path = Path(video_path_text) if video_path_text else None  # 构造视频路径对象。
        if audio_feature is None or not audio_feature.exists():  # 如果音频特征文件不可用。
            raise ValueError("真实 Ultralight 推理完成后未找到音频特征文件。")  # 抛出明确异常。
        if video_path is None or not video_path.exists():  # 如果输出视频不存在。
            raise ValueError("真实 Ultralight 推理完成后未找到输出视频。")  # 抛出明确异常。
        if video_path.stat().st_size <= 0:  # 如果输出视频为空文件。
            raise ValueError("真实 Ultralight 推理输出视频为空，请检查推理日志。")  # 抛出明确异常。
        return payload  # 返回通过校验的推理结果。

    def _mock_avatar_response(self, persona: dict[str, Any], script_lines: list[str], job_id: str, answer_text: str) -> str:  # 在模拟模式下生成推理结果。
        job_dir = self._job_dir("avatar", job_id)  # 获取数字人任务输出目录。
        script_path = job_dir / "avatar_script.txt"  # 计算脚本文件路径。
        script_path.write_text("\n".join(script_lines), encoding="utf-8")  # 写入模拟口播脚本文件。
        output_video = job_dir / "avatar_output.mp4"  # 计算模拟输出视频路径。
        output_video.write_bytes(b"")  # 生成空白占位视频文件。
        result_payload = {  # 构造模拟推理结果清单。
            "persona_name": persona.get("name", "默认数字人"),  # 记录数字人名称。
            "profile": self.settings.ultralight_profile,  # 记录当前配置名。
            "script_path": str(script_path),  # 记录脚本路径。
            "avatar_image": "",  # 记录头像图片路径占位值。
            "audio_path": "",  # 记录驱动音频路径占位值。
            "audio_feature": "",  # 记录驱动特征路径占位值。
            "dataset_dir": str(persona.get("ultralight_dataset_dir", "")),  # 记录画像中的数据目录。
            "checkpoint": str(persona.get("ultralight_checkpoint_path", "")),  # 记录画像中的权重路径。
            "video_path": str(output_video),  # 记录输出视频路径。
            "answer_text": answer_text,  # 记录原始回答文本。
            "status": "prepared",  # 记录完成状态。
            "mode": "mock",  # 标记当前为模拟模式。
        }  # 完成结果对象构造。
        result_path = job_dir / "avatar_result.json"  # 计算结构化结果路径。
        result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 写入模拟结果文件。
        return str(result_path)  # 返回结果文件路径。

    def render_avatar_response(self, persona: dict[str, Any], script_lines: list[str], job_id: str, answer_text: str, assets: list[dict[str, Any]]) -> str:  # 执行真实 Ultralight 推理。
        if self.settings.use_mock_response:  # 如果当前处于模拟模式。
            return self._mock_avatar_response(persona, script_lines, job_id, answer_text)  # 直接返回模拟推理结果。
        root = self._require_ultralight_root()  # 获取有效的 Ultralight 根目录。
        self._require_ffmpeg()  # 校验 ffmpeg 命令可用。
        job_dir = self._job_dir("avatar", job_id)  # 获取数字人任务目录。
        script_path = job_dir / "avatar_script.txt"  # 计算脚本文件路径。
        script_path.write_text("\n".join(script_lines), encoding="utf-8")  # 写入口播脚本文件。
        assets_by_id = {str(item.get("asset_id", "")): item for item in assets}  # 构造素材主键索引。
        avatar_image = self._pick_avatar_image(persona, assets_by_id)  # 选择头像图片。
        dataset_dir_text = str(persona.get("ultralight_dataset_dir", "")).strip()  # 读取画像中记录的数据目录。
        checkpoint_text = str(persona.get("ultralight_checkpoint_path", "")).strip()  # 读取画像中记录的权重路径。
        if not dataset_dir_text or not checkpoint_text:  # 如果数字人画像未绑定训练产物。
            raise ValueError("数字人未绑定真实 Ultralight 训练结果，请先把训练产物路径写入画像字段。")  # 抛出明确异常。
        dataset_dir = Path(dataset_dir_text)  # 构造训练数据目录路径对象。
        checkpoint_path = Path(checkpoint_text)  # 构造训练权重路径对象。
        if not dataset_dir.exists() or not checkpoint_path.exists():  # 如果关键训练产物不存在。
            raise ValueError("数字人画像中的 Ultralight 数据目录或权重路径不存在。")  # 抛出明确异常。
        tts_wav = job_dir / "tts.wav"  # 计算驱动音频路径。
        audio_feature = job_dir / ("tts_hu.npy" if self.settings.ultralight_asr == "hubert" else "tts_wenet.npy")  # 计算音频特征路径。
        output_video = job_dir / "avatar_output.mp4"  # 计算输出视频路径。
        if self.settings.external_tts_command:  # 如果配置了外部 TTS 命令模板。
            tts_cmd = [item.format(text=answer_text, output=str(tts_wav), script=str(script_path)) for item in self.settings.external_tts_command.split()]  # 渲染外部 TTS 命令。
            self._run(tts_cmd, root, job_dir / "tts.log")  # 执行外部 TTS 命令。
        elif self.settings.ultralight_audio_wav and Path(self.settings.ultralight_audio_wav).exists():  # 如果配置了固定驱动音频文件。
            shutil.copy2(self.settings.ultralight_audio_wav, tts_wav)  # 复制固定音频作为驱动源。
        else:  # 如果既没有外部 TTS 也没有固定驱动音频。
            raise ValueError("真实 Ultralight 推理需要配置 EXTERNAL_TTS_COMMAND 或 ULTRALIGHT_AUDIO_WAV。")  # 抛出明确异常。
        if self.settings.ultralight_asr == "hubert":  # 如果使用 hubert 模式。
            feat_cmd = self._python_cmd() + [str(root / "data_utils" / "hubert.py"), "--wav", str(tts_wav), "--out", str(audio_feature)]  # 构造 HuBERT 特征提取命令。
        else:  # 如果使用 wenet 模式。
            feat_cmd = self._python_cmd() + [str(root / "data_utils" / "wenet_infer.py"), str(tts_wav)]  # 构造 WeNet 特征提取命令。
        self._run(feat_cmd, root / "data_utils" if self.settings.ultralight_asr == "wenet" else root, job_dir / "audio_feature.log")  # 执行音频特征提取命令。
        if self.settings.ultralight_asr == "wenet" and not audio_feature.exists():  # 如果是 wenet 且输出不在目标路径。
            generated = tts_wav.with_name(tts_wav.stem + "_wenet.npy")  # 按官方脚本规则推断输出文件名。
            if generated.exists():  # 如果官方输出文件存在。
                shutil.move(str(generated), str(audio_feature))  # 移动到统一目标路径。
        inference_cmd = self._python_cmd() + [str(root / "inference.py"), "--asr", self.settings.ultralight_asr, "--dataset", str(dataset_dir), "--audio_feat", str(audio_feature), "--save_path", str(output_video), "--checkpoint", str(checkpoint_path), "--audio_wav", str(tts_wav)]  # 构造推理命令。
        self._run(inference_cmd, root, job_dir / "inference.log")  # 执行真实推理命令。
        result_payload = {  # 构造推理结果清单。
            "persona_name": persona.get("name", "默认数字人"),  # 记录数字人名称。
            "profile": self.settings.ultralight_profile,  # 记录当前配置名。
            "script_path": str(script_path),  # 记录脚本路径。
            "avatar_image": avatar_image,  # 记录头像图片路径。
            "audio_path": str(tts_wav),  # 记录驱动音频路径。
            "audio_feature": str(audio_feature),  # 记录驱动特征路径。
            "dataset_dir": str(dataset_dir),  # 记录数据目录。
            "checkpoint": str(checkpoint_path),  # 记录推理权重路径。
            "video_path": str(output_video),  # 记录输出视频路径。
            "answer_text": answer_text,  # 记录原始回答文本。
            "status": "prepared",  # 记录完成状态。
            "mode": "real",  # 标记当前为真实模式。
        }  # 完成结果对象构造。
        result_path = job_dir / "avatar_result.json"  # 计算结构化结果路径。
        result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")  # 写入结果文件。
        self._validate_avatar_result(result_path)  # 校验真实推理产物是否齐全。
        return str(result_path)  # 返回结果文件路径。
