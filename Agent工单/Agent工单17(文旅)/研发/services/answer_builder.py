# 这里负责把检索结果组织成前端需要的输出结构。
from services.llm_client import LlmClient
from services.multimodal_tools import build_audio_payload


class AnswerBuilder:
    """这里封装答案生成逻辑。"""

    def __init__(self, deepseek_client: LlmClient, qwen_client: LlmClient):
        # 这里保存 DeepSeek 客户端。
        self.deepseek_client = deepseek_client
        # 这里保存千问客户端。
        self.qwen_client = qwen_client

    def get_client(self, provider: str) -> LlmClient:
        # 这里按 provider 选择模型客户端。
        return self.qwen_client if provider == "qwen" else self.deepseek_client

    def build_multimodal_block(self, record: dict):
        # 这里构建多模态推荐块。
        return {"图片推荐": record.get("image_keywords", []), "视频推荐": record.get("video_keywords", []), "音频推荐": record.get("audio_keywords", []), "字幕支持": "支持中文字幕与无障碍辅助"}

    def append_tts_block(self, answer: dict):
        # 这里提取用于语音播报的文本。
        text = answer.get("生成内容") or answer.get("guide_text") or ""
        # 这里追加更真实的 TTS 演示数据。
        answer["语音播报"] = build_audio_payload(text)
        return answer

    def merge_answer(self, template_answer: dict, record: dict, mode: str, language: str, query: str, provider: str):
        # 这里尝试调用指定模型生成更自然的讲解。
        generated = self.get_client(provider).generate_text(record, mode, language, query)
        # 这里判断是否拿到了模型结果。
        if generated:
            # 这里优先使用模型结果覆盖模板主文案。
            if language == "en":
                template_answer["guide_text"] = generated
            else:
                template_answer["生成内容"] = generated
        # 这里追加多模态输出信息。
        template_answer["多模态输出"] = self.build_multimodal_block(record)
        # 这里补充语音播报区块。
        return self.append_tts_block(template_answer)

    def build_multimodal_answer(self, record: dict, query: str, provider: str, image_hint: str = "", image_bytes: bytes = b"", filename: str = "upload.png"):
        # 这里调用多模态接口尝试生成图片线索讲解。
        generated = self.get_client(provider).generate_multimodal(query, image_hint, image_bytes=image_bytes, filename=filename)
        # 这里返回多模态结果。
        return generated or record.get("guide", "")
