"""
src/llm/dialogue.py - LLM 对话客户端 (流式句子版)
功能: 对接 DeepSeek/Ollama/vLLM/OpenAI API 实现流式对话生成。
      新增 chat_stream_sentences() 方法: 流式产出完整句子。
      保留 chat()/chat_stream() 向后兼容。
      对应工单需求: "对话对接大模型服务实现实时生成数字人对话视频"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    LLM 对话客户端 (多后端兼容)。
    使用 OpenAI 兼容协议，支持 DeepSeek/Ollama/vLLM/OpenAI。
    支持流式输出 + 句子级分句。
    """

    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-chat", max_tokens: int = 2048,
                 temperature: float = 0.7):
        """
        初始化 LLM 客户端。
        参数:
            api_key: API 密钥
            api_base: API 基础地址
            model: 模型名称
            max_tokens: 最大生成 token 数
            temperature: 生成随机性(0-1)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_base = api_base
        self.api_key = api_key
        self.client = None

        if not api_key:
            logger.warning(
                "API Key未设置！对话功能暂不可用。"
                "请设置环境变量: export DEEPSEEK_API_KEY=your-key"
            )
        else:
            self._create_client()

    def _create_client(self):
        """创建异步 OpenAI 兼容客户端，并增加更稳的超时配置。"""
        if self.api_key:
            import httpx
            transport = httpx.AsyncHTTPTransport(retries=2)
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)
            http_client = httpx.AsyncClient(timeout=timeout, transport=transport)
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base,
                http_client=http_client,
            )
            logger.info(f"LLM客户端就绪: base={self.api_base}, model={self.model}")

    def _ensure_client(self):
        """确保客户端已创建。"""
        if self.client is None:
            if not self.api_key:
                raise RuntimeError(
                    "LLM API Key未设置！请在终端执行:\n"
                    "  export DEEPSEEK_API_KEY=sk-你的key\n"
                    "然后重新运行 python run.py"
                )
            self._create_client()

    async def chat(self, messages: list) -> str:
        """
        非流式对话请求，返回完整回复。
        参数:
            messages: [{"role":"system","content":"..."},
                       {"role":"user","content":"..."}]
        返回: 模型生成的回复文本
        """
        self._ensure_client()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=self.max_tokens, temperature=self.temperature,
                stream=False,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM API调用失败: {e}")
            return f"抱歉，我暂时无法回答。(错误: {e})"

    async def chat_stream(self, messages: list) -> str:
        """
        流式对话接口。逐token接收回复，降低首字延迟。
        参数:
            messages: 消息列表
        返回: 拼接后的完整回复文本
        """
        self._ensure_client()
        try:
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=self.max_tokens, temperature=self.temperature,
                stream=True,
            )
            chunks = []
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    chunks.append(chunk.choices[0].delta.content)
            return "".join(chunks).strip()
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            return await self.chat(messages)  # 回退非流式

    async def chat_stream_sentences(self, messages: list,
                                     min_sentence_chars: int = 4,
                                     max_sentence_chars: int = 80,
                                     interrupt_check=None) -> AsyncIterator[str]:
        """
        流式对话接口 — 句子级产出。
        每检测到一个完整句子立即yield，供TTS并行处理。
        参数:
            messages: 消息列表
            min_sentence_chars: 最小句子长度(低于不分句)
            max_sentence_chars: 最大句子长度(超过强制分句)
            interrupt_check: 可选回调，返回 True 表示应中断流式生成
        Yields:
            完整句子文本，一次一个
        """
        from src.core.streaming import SentenceBuffer

        self._ensure_client()
        buffer = SentenceBuffer(min_chars=min_sentence_chars,
                                max_chars=max_sentence_chars)
        try:
            stream = await self.client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=self.max_tokens, temperature=self.temperature,
                stream=True,
            )
            async for chunk in stream:
                # 逐 token 级打断检查，实现"自然打断"
                if interrupt_check and interrupt_check():
                    logger.info("LLM流式生成被用户打断")
                    break
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    sentence = buffer.feed(token)
                    if sentence:
                        yield sentence
            # 流结束或被打断，flush剩余的
            final = buffer.flush()
            if final:
                yield final
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            # 回退: 非流式获取完整回复，整体作为一个句子产出
            full = await self.chat(messages)
            if full:
                yield full


def create_llm_client(config) -> DeepSeekClient:
    """
    LLM客户端工厂函数。
    根据配置创建对应的客户端，自动匹配各后端的默认 base_url 和模型。
    """
    provider = getattr(config.llm, 'provider', 'deepseek')
    api_key = config.llm.api_key

    # 各后端默认配置
    provider_defaults = {
        "deepseek": {"base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
        "ollama": {"base": "http://localhost:11434/v1", "model": "qwen2.5:7b"},
        "vllm": {"base": "http://localhost:8000/v1", "model": "qwen2.5-7b-instruct"},
        "openai": {"base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    }
    defaults = provider_defaults.get(provider, provider_defaults["deepseek"])

    # 如果用户显式设置了非默认 api_base，保留用户的设置；
    # 否则使用 provider 对应的默认地址
    yaml_api_base = getattr(config.llm, 'api_base', '')
    provider_base = defaults["base"]
    if yaml_api_base and yaml_api_base != provider_base:
        api_base = yaml_api_base  # 用户显式覆盖
    else:
        api_base = provider_base   # 使用后端默认

    # 模型同理：优先使用用户显式配置，否则用后端默认
    yaml_model = config.llm.model
    if yaml_model and yaml_model != "deepseek-chat":
        model = yaml_model
    else:
        model = defaults["model"]

    if provider == "ollama":
        api_key = api_key or "ollama"  # Ollama不需要真实key

    return DeepSeekClient(
        api_key=api_key,
        api_base=api_base,
        model=model,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature,
    )
