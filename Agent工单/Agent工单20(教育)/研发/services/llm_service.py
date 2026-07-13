# 工单20：本文件用于封装 DeepSeek 与千问兼容接口调用。
# 工单20：导入JSON处理工具。
import json  # 工单20：代码语句。
# 工单20：导入OpenAI兼容客户端。
from openai import OpenAI  # 工单20：代码语句。

# 工单20：定义大模型服务类。
class LLMService:  # 工单20：代码语句。
    # 工单20：初始化模型配置。
    def __init__(self, settings: dict):  # 工单20：代码语句。
        # 工单20：保存配置字典。
        self.settings = settings  # 工单20：代码语句。

    # 工单20：定义提供方信息获取函数。
    def get_provider_meta(self, provider: str) -> dict:  # 工单20：代码语句。
        # 工单20：深度求索分支返回配置。
        if provider == "deepseek":  # 工单20：代码语句。
            return {  # 工单20：代码语句。
                "base_url": self.settings.get("deepseek_base_url"),  # 工单20：代码语句。
                "api_key": self.settings.get("deepseek_api_key"),  # 工单20：代码语句。
                "model": self.settings.get("deepseek_model"),  # 工单20：代码语句。
                "label": "DeepSeek",  # 工单20：代码语句。
            }  # 工单20：代码语句。
        # 工单20：默认返回千问配置。
        return {  # 工单20：代码语句。
            "base_url": self.settings.get("qwen_base_url"),  # 工单20：代码语句。
            "api_key": self.settings.get("qwen_api_key"),  # 工单20：代码语句。
            "model": self.settings.get("qwen_text_model"),  # 工单20：代码语句。
            "label": "千问",  # 工单20：代码语句。
        }  # 工单20：代码语句。

    # 工单20：定义模型状态查询函数。
    def get_status(self) -> dict:  # 工单20：代码语句。
        # 工单20：返回两个模型的可用性状态。
        return {  # 工单20：代码语句。
            "deepseek": bool(self.settings.get("deepseek_api_key")),  # 工单20：代码语句。
            "qwen": bool(self.settings.get("qwen_api_key")),  # 工单20：代码语句。
            "default_provider": self.settings.get("default_provider", "deepseek"),  # 工单20：代码语句。
        }  # 工单20：代码语句。

    # 工单20：定义复盘增强函数。
    def enhance_review(self, review: dict, interview: dict, provider: str) -> dict:  # 工单20：代码语句。
        # 工单20：读取提供方配置。
        meta = self.get_provider_meta(provider)  # 工单20：代码语句。
        # 工单20：密钥缺失时直接返回本地结果。
        if not meta.get("api_key"):  # 工单20：代码语句。
            review["llm_summary"] = f"{meta['label']} 未配置密钥，当前展示本地规则生成结果。"  # 工单20：代码语句。
            return review  # 工单20：代码语句。
        # 工单20：构造系统提示词。
        system_prompt = "你是教育场景中的面试复盘助手，请输出严格JSON，字段包括overall_comment,self_intro_comment,suggestions。"  # 工单20：代码语句。
        # 工单20：构造用户输入内容。
        user_prompt = {  # 工单20：代码语句。
            "student_name": interview.get("student_name"),  # 工单20：代码语句。
            "position_name": interview.get("position_name"),  # 工单20：代码语句。
            "question_analysis": review.get("question_analysis"),  # 工单20：代码语句。
            "full_transcript": interview.get("full_transcript", ""),  # 工单20：代码语句。
            "self_intro": interview.get("self_intro", ""),  # 工单20：代码语句。
        }  # 工单20：代码语句。
        # 工单20：实例化兼容客户端。
        client = OpenAI(api_key=meta["api_key"], base_url=meta["base_url"])  # 工单20：代码语句。
        try:  # 工单20：代码语句。
            # 工单20：调用聊天补全接口。
            response = client.chat.completions.create(  # 工单20：代码语句。
                model=meta["model"],  # 工单20：代码语句。
                temperature=0.3,  # 工单20：代码语句。
                response_format={"type": "json_object"},  # 工单20：代码语句。
                messages=[  # 工单20：代码语句。
                    {"role": "system", "content": system_prompt},  # 工单20：代码语句。
                    {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},  # 工单20：代码语句。
                ],  # 工单20：代码语句。
            )  # 工单20：代码语句。
            # 工单20：读取模型文本内容。
            content = response.choices[0].message.content or "{}"  # 工单20：代码语句。
            # 工单20：解析模型输出JSON。
            payload = json.loads(content)  # 工单20：代码语句。
            # 工单20：用模型结果覆盖总体评价信息。
            review["overall_comment"] = payload.get("overall_comment", review.get("overall_comment"))  # 工单20：代码语句。
            review["self_intro_comment"] = payload.get("self_intro_comment", review.get("self_intro_comment"))  # 工单20：代码语句。
            review["suggestions"] = payload.get("suggestions", review.get("suggestions"))  # 工单20：代码语句。
            # 工单20：记录模型增强说明。
            review["llm_summary"] = f"已使用{meta['label']}完成总体评价增强。"  # 工单20：代码语句。
            # 工单20：返回增强后的结果。
            return review  # 工单20：代码语句。
        except Exception as exc:  # 工单20：代码语句。
            # 工单20：调用失败时保留本地结果。
            review["llm_summary"] = f"{meta['label']} 调用失败，已回退到本地规则：{exc}"  # 工单20：代码语句。
            # 工单20：返回回退结果。
            return review  # 工单20：代码语句。
