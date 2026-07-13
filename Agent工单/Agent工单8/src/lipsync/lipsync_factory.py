"""
src/lipsync/lipsync_factory.py - 唇形同步引擎工厂
功能: 统一的唇形同步引擎创建接口，支持Wav2Lip/MuseTalk/ERNerf。
      根据配置自动选择模型，支持运行时切换。
      对应工单需求: "兼容多种数字人模型(ERNerf/MuseTalk/Wav2Lip)，支持模型切换"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class LipSyncModel(Enum):
    """唇形同步模型枚举。"""
    WAV2LIP = "wav2lip"
    MUSETALK = "musetalk"
    ERNERF = "ernerf"
    SADTALKER = "sadtalker"  # 已有模型，零下载


def create_lipsync_engine(config) -> object:
    """
    唇形同步引擎工厂函数。
    根据配置选择并初始化对应的引擎。
    参数:
        config: AppConfig实例
    返回:
        Wav2LipEngine / MuseTalkEngine / ERNerfEngine 实例
    """
    model_name = config.lipsync.model

    if model_name == LipSyncModel.WAV2LIP.value:
        from src.lipsync.wav2lip_engine import Wav2LipEngine
        return Wav2LipEngine(
            checkpoint_path=config.lipsync.checkpoint,
            device=config.gpu.device,
            img_size=config.lipsync.img_size,
            use_fp16=config.gpu.use_fp16,
        )

    elif model_name == LipSyncModel.MUSETALK.value:
        try:
            from src.lipsync.musetalk_engine import MuseTalkEngine
            return MuseTalkEngine(
                checkpoint_path=getattr(config.lipsync, 'musetalk_checkpoint',
                                        "models/musetalk/pytorch_model.bin"),
                device=config.gpu.device,
                use_fp16=config.gpu.use_fp16,
            )
        except ImportError as e:
            logger.error(f"MuseTalk导入失败: {e}")
            raise RuntimeError(
                "MuseTalk未安装。请参考: https://github.com/TMElyralab/MuseTalk"
            )

    elif model_name == LipSyncModel.ERNERF.value:
        try:
            from src.lipsync.ernerf_engine import ERNerfEngine
            return ERNerfEngine(
                checkpoint_path=getattr(config.lipsync, 'ernerf_checkpoint',
                                        "models/ernerf/model.ckpt"),
                device=config.gpu.device,
            )
        except ImportError as e:
            logger.error(f"ERNerf导入失败: {e}")
            raise RuntimeError(
                "ERNerf未安装。请参考: https://github.com/Fictionarry/ER-NeRF"
            )

    elif model_name == LipSyncModel.SADTALKER.value:
        from src.lipsync.sadtalker_engine import SadTalkerEngine
        engine = SadTalkerEngine(
            device=config.gpu.device,
            img_size=config.lipsync.img_size,
            use_fp16=config.gpu.use_fp16,
            sadtalker_root=getattr(config.lipsync, 'sadtalker_root', ''),
            output_size=config.pipeline.video_height,
        )
        # 加载模型并做推理烟雾测试
        try:
            engine.load_model()
            if engine._model is not None:
                # 烟雾测试: 使用真实头像 + 短音频做完整推理验证
                import numpy as np
                test_audio = np.random.randn(8000).astype(np.float32) * 0.05
                try:
                    # 不提前调用 extract_features，避免零音频缓存触发错误推理路径
                    mel_features = engine.extract_features(test_audio)
                    if mel_features.shape[0] >= 3:
                        # 只用前3帧做推理，测试管线通畅即可
                        test_frames = engine.generate_frames(
                            mel_features[:3])
                        is_real = (test_frames is not None and
                                  test_frames.shape[0] > 0 and
                                  float(np.std(test_frames[0])) > 1.0)
                        if is_real:
                            logger.info("LipSync: SadTalker 就绪 ✓")
                            engine.reset_buffer()
                            return engine
                        else:
                            logger.warning(
                                "LipSync: SadTalker 加载成功但推理产出占位帧"
                                f"(std={float(np.std(test_frames[0])):.1f})，回退 SimpleLipSync"
                            )
                    else:
                        logger.warning("LipSync: Mel特征不足，回退 SimpleLipSync")
                except Exception as smoke_err:
                    logger.warning(f"LipSync: SadTalker 烟雾测试异常: {smoke_err}")
                    logger.warning("LipSync: 回退到 SimpleLipSync")
            else:
                logger.warning("LipSync: SadTalker 模型加载失败，回退到 SimpleLipSync")
        except Exception as e:
            logger.warning(f"LipSync: SadTalker 异常 ({e})，回退到 SimpleLipSync")
        # Fallback: 简单但有效的唇形动画
        from src.lipsync.simple_lipsync_engine import SimpleLipSyncEngine
        logger.info("LipSync: 使用 SimpleLipSync (轻量唇形动画引擎)")
        return SimpleLipSyncEngine(
            img_size=config.lipsync.img_size,
            output_size=config.pipeline.video_height,
        )
    elif model_name == "simple":
        from src.lipsync.simple_lipsync_engine import SimpleLipSyncEngine
        return SimpleLipSyncEngine(
            img_size=config.lipsync.img_size,
            output_size=config.pipeline.video_height,
        )
    else:
        logger.warning(f"未知唇形同步模型'{model_name}'，回退到Wav2Lip")
        from src.lipsync.wav2lip_engine import Wav2LipEngine
        return Wav2LipEngine(
            checkpoint_path=config.lipsync.checkpoint,
            device=config.gpu.device,
            img_size=config.lipsync.img_size,
            use_fp16=config.gpu.use_fp16,
        )
