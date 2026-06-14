# -*- coding: utf-8 -*-
"""
主入口模块 — 依次调用全部模块，完成VLM微调全流程。

功能说明：
1. 加载配置（config.py）
2. 数据准备：IMDR数据→VLM微调JSONL（data_prep.py）
3. 生成LLaMA-Factory LoRA配置（train_config.py）
4. 启动LoRA微调训练（trainer.py）
5. 执行专业评估：Qwen2.5-VL:3b + MiMo双模型对比（evaluator.py）
6. 打印评估报告摘要

用法:
  python run.py                          # 完整流水线（模拟模式）
  python run.py --real                   # 真实模式（调用API评估）
  python run.py --vlm                    # 真实模式 + VLM评估（Qwen2.5-VL:3b）
  python run.py --compare                # 双模型对比模式
  python run.py --data-only              # 只做数据准备
  python run.py --extract-images         # 数据准备时提取PDF图片
  python run.py --help                   # 帮助信息
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import sys  # 导入sys模块，用于处理命令行参数
import os  # 导入os模块

# 将父目录和各子目录加入sys.path，支持跨目录导入
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "优化", "部署"]:
    _p = os.path.join(_BASE_DIR, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)


def print_banner():
    """打印项目启动横幅"""
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║     VLM微调流水线 (Vision-Language Model)     ║")
    logger.info("║     工单16 - 调试与微调专用视觉语言模型       ║")
    logger.info("║     Qwen2.5-VL:3b (Ollama) 图片识别评估      ║")
    logger.info("╚══════════════════════════════════════════════╝")
    logger.info("")


def run_pipeline(mock_api=True, use_vlm=False, compare=False,
                 extract_images=False):
    """
    执行完整VLM微调流水线。

    参数:
        mock_api: 是否模拟API调用（True=模拟，False=真实调用）
        use_vlm: 是否使用Qwen2.5-VL:3b进行视觉评估
        compare: 是否执行双模型对比评估
        extract_images: 数据准备时是否从PDF提取图片
    """
    print_banner()  # 打印横幅

    import config  # 导入配置模块

    # ==================== Step 1: 加载配置 ====================
    logger.info("=" * 50)
    logger.info("[Step 1/5] 加载配置...")
    logger.info(f"  数据文件: {config.QUESTIONS_FILE}")
    logger.info(f"  Ollama模型: {config.OLLAMA_VLM_MODEL}")
    logger.info(f"  MiMo API: {config.MIMO_BASE_URL}")
    logger.info(f"  基础模型: {config.BASE_MODEL}")
    logger.info(f"  输出目录: {config.OUTPUT_DIR}")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)  # 确保输出目录存在

    # ==================== Step 2: 数据准备 ====================
    logger.info("\n" + "=" * 50)
    logger.info("[Step 2/5] 数据准备 - IMDR→VLM微调格式...")

    # 检查PDF目录
    pdf_dir = config.PDF_DIR
    if extract_images:
        logger.info(f"  🖼️  图片提取已启用")
        logger.info(f"  📁 PDF目录: {pdf_dir}")
        if not os.path.exists(pdf_dir):
            logger.warning(f"  ⚠️ PDF目录不存在！请先准备专利PDF文件")
            logger.info(f"  💡 从工单附件复制: 工单/RAG 新工单/14-17附件/original_problems/original_problems/documents/")

    from data_prep import convert_imdr_to_vlm
    stats = convert_imdr_to_vlm(
        config.QUESTIONS_FILE,
        config.OUTPUT_DIR,
        pdf_dir=pdf_dir if extract_images else None,
        images_dir=config.IMAGES_DIR if extract_images else None,
        extract_images=extract_images,
        max_pdfs=50,  # 只处理前50份PDF，避免全部提取太慢
    )
    logger.info(f"  ✅ 总计 {stats['total']} 条 | "
          f"训练 {stats['train']} | 验证 {stats['val']} | 测试 {stats['test']}")
    if extract_images:
        logger.info(f"  🖼️  提取图片: {stats['extracted_images']} 张")

    # ==================== Step 3: 生成配置 ====================
    logger.info("\n" + "=" * 50)
    logger.info("[Step 3/5] 生成LLaMA-Factory LoRA配置...")
    from train_config import generate_lora_config, print_training_command
    yaml_path = generate_lora_config(config, config.OUTPUT_DIR)
    print_training_command(yaml_path)

    # ==================== Step 4: 启动微调 ====================
    logger.info("\n" + "=" * 50)
    logger.info("[Step 4/5] 启动LoRA微调训练...")
    from trainer import check_environment, run_training
    env_status = check_environment(config)
    # 根据环境自动选择模式
    use_mock = not (env_status.get("llamafactory_installed") and
                   env_status.get("cli_available"))
    if use_mock:
        logger.warning("  ⚠️ LLaMA-Factory CLI不可用，使用模拟训练模式")
    train_result = run_training(config, yaml_path, mock_mode=use_mock)
    if train_result["success"]:
        logger.info(f"  ✅ 训练完成！输出: {train_result.get('output_dir', 'N/A')}")
    else:
        logger.error(f"  ❌ 训练失败: {train_result.get('error', '未知错误')}")

    # ==================== Step 5: 专业评估 ====================
    logger.info("\n" + "=" * 50)
    logger.info("[Step 5/5] 实施专业评估...")
    from evaluator import load_eval_set, run_evaluation

    # 加载评估集
    eval_path = os.path.join(config.OUTPUT_DIR, "eval_set.json")
    if os.path.exists(eval_path):
        eval_data = load_eval_set(eval_path)
    else:
        logger.warning("  ⚠️ 评估集不存在，跳过评估")
        eval_data = []

    if eval_data:
        # 初始化Ollama VLM客户端（如果需要）
        vlm_client = None
        if use_vlm or compare:
            try:
                from vlm_client import OllamaVLM
                vlm_client = OllamaVLM(
                    model=config.OLLAMA_VLM_MODEL,
                    base_url=config.OLLAMA_BASE_URL,
                    timeout=config.OLLAMA_TIMEOUT,
                )
                # 检查Ollama服务
                svc_ok, svc_msg = vlm_client.check_health()
                if svc_ok:
                    logger.info(f"  ✅ Ollama服务: {svc_msg}")
                else:
                    logger.warning(f"  ⚠️ Ollama服务: {svc_msg}")
                    logger.info(f"  💡 请在WSL终端启动: ollama serve")
                    vlm_client = None
            except ImportError:
                logger.warning("  ⚠️ vlm_client模块未找到")
            except Exception as e:
                logger.warning(f"  ⚠️ Ollama客户端初始化失败: {e}")

        # 执行评估
        report = run_evaluation(
            config, eval_data,
            vlm_client=vlm_client,
            mock_api=mock_api,
            compare_mode=compare
        )

        # 判断是否达标（取两个模型中较好的）
        best_acc = max(
            m["accuracy"]
            for m in report.get("models", {}).values()
        ) if report.get("models") else 0

        if best_acc >= 80:
            logger.info(f"\n✅ 达标！最佳准确率 ≥ 80%")
        else:
            logger.warning(f"\n⚠️ 未达标，建议优化微调策略")
    else:
        logger.warning("  ⚠️ 无评估数据，跳过评估")

    # ==================== 完成 ====================
    logger.info("\n" + "=" * 50)
    logger.info("流水线执行完成！")
    logger.info(f"  所有产出物已保存到: {config.OUTPUT_DIR}")

    # 打印Windows运行指引
    logger.info("\n" + "=" * 50)
    logger.info("Windows 环境运行指引")
    logger.info(f"  cd {config.BASE_DIR}")
    logger.info(f"\n  # 【推荐】在Windows PyCharm中运行:")
    logger.info(f"  python run.py --vlm          # 使用Qwen2.5-VL:3b评估")
    logger.info(f"  python run.py --compare      # 双模型对比（MiMo vs Qwen2.5-VL）")
    logger.info(f"  python run.py --data-only    # 只做数据准备")
    logger.info(f"\n  # 注意:")
    logger.info(f"  1. Qwen2.5-VL:3b评估需要Ollama在WSL运行: ollama serve")
    logger.info(f"  2. LLaMA-Factory微调需要下载Qwen2.5-VL-3B-Instruct完整模型")
    logger.info(f"  3. 从ModelScope下载: modelscope download Qwen/Qwen2.5-VL-3B-Instruct")
    logger.info(f"  4. 如果显存不足(8GB)，调小 BATCH_SIZE=1, GRADIENT_ACCUMULATION=8")
    logger.info("=" * 50)


def main():
    """
    主函数：处理命令行参数，执行对应操作。
    """
    args = sys.argv[1:]  # 获取命令行参数

    if "--help" in args or "-h" in args:  # 帮助
        logger.info("用法:")
        logger.info("  python run.py                    完整流水线（模拟模式）")
        logger.info("  python run.py --real             真实模式（调用MiMo API评估）")
        logger.info("  python run.py --vlm              真实模式 + Qwen2.5-VL:3b评估")
        logger.info("  python run.py --compare          双模型对比评估模式")
        logger.info("  python run.py --data-only        只做数据准备")
        logger.info("  python run.py --extract-images   数据准备时从PDF提取图片")
        logger.info("  python run.py --help             帮助信息")
        return

    if "--data-only" in args:  # 只做数据准备
        print_banner()
        import config
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        extract_images = "--extract-images" in args
        from data_prep import convert_imdr_to_vlm
        stats = convert_imdr_to_vlm(
            config.QUESTIONS_FILE,
            config.OUTPUT_DIR,
            pdf_dir=config.PDF_DIR if extract_images else None,
            images_dir=config.IMAGES_DIR if extract_images else None,
            extract_images=extract_images
        )
        logger.info(f"\n✅ 数据准备完成！共 {stats['total']} 条")
        return

    # 判断运行模式
    mock_api = "--real" not in args
    use_vlm = "--vlm" in args
    compare = "--compare" in args
    extract_images = "--extract-images" in args

    if mock_api:
        logger.info("模拟模式：API调用将使用模拟数据")
    else:
        logger.info("真实模式：将调用真实API进行评估")

    if use_vlm:
        logger.info("VLM评估：使用Qwen2.5-VL:3b进行视觉问答")
    if compare:
        logger.info("对比模式：将比较MiMo基线 vs Qwen2.5-VL")

    run_pipeline(
        mock_api=mock_api,
        use_vlm=use_vlm,
        compare=compare,
        extract_images=extract_images,
    )



def _setup_logging():
    """配置全局日志格式和级别。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    _setup_logging()  # 初始化日志配置

    main()
