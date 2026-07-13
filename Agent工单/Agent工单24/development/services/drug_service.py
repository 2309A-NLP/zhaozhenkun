"""该文件用于接入真实药品标签接口并输出药品公开信息摘要。"""

# 导入正则模块，用于从问题中抽取药品名称。
import re

# 导入公共 HTTP 客户端，便于访问公开药品接口。
from development.services.http_client import HttpJsonClient

# 定义常见中文药名到英文通用名的映射，提升 openFDA 命中率。
DRUG_ALIAS_MAP = {
    "布洛芬": "ibuprofen",
    "对乙酰氨基酚": "acetaminophen",
    "阿莫西林": "amoxicillin",
    "头孢": "cephalosporin",
    "阿司匹林": "aspirin",
    "氯雷他定": "loratadine",
}

# 定义常见提问前缀，用于清理药名抽取前的噪声文本。
HELPER_PREFIXES = (
    "帮我查询一下",
    "帮我查一下",
    "请查询一下",
    "请查一下",
    "查询一下",
    "查一下",
    "帮我",
    "请",
    "麻烦",
)


# 定义药品查询服务，用于访问 openFDA 药品标签接口。
class DrugService:
    # 初始化药品查询服务，并注入底层 HTTP 客户端。
    def __init__(self, http_client: HttpJsonClient | None = None) -> None:
        # 保存 HTTP 客户端对象，便于复用连接。
        self.http_client = http_client or HttpJsonClient()

    # 根据用户问题查询药品公开信息并返回摘要。
    def lookup(self, query: str) -> str:
        # 从用户问题中尽量抽取药品名称。
        original_name = self.extract_drug_name(query)
        # 若无法识别药名，则引导用户明确药品名称。
        if not original_name:
            return "未识别到明确药品名称，请在问题中写出药名后再查询。"
        # 将中文别名等归一化为更容易命中的查询词。
        search_name = self.normalize_drug_name(original_name)
        # 逐个字段尝试查询公开药品标签记录。
        record = self._search_record(search_name)
        # 若未查到结果，则给出更明确的边界提示。
        if not record:
            return f"未在 openFDA 查询到“{original_name}”的公开标签信息，建议尝试英文通用名或国际商品名。"
        # 将查询结果格式化为可读摘要文本。
        return self._format_record(original_name, record)

    # 从用户问题中抽取最可能的药品名称。
    def extract_drug_name(self, query: str) -> str:
        # 先移除常见的礼貌前缀与查询前缀。
        cleaned = self._strip_prefixes(query.strip())
        # 定义常见药品提问模式集合。
        patterns = [
            r"([一-龥A-Za-z0-9\- ]{2,40}?)(?:有哪些副作用|副作用|说明书|用量|禁忌|适应症|可以治什么|治什么)",
            r"([一-龥A-Za-z0-9\- ]{2,40}?)怎么吃",
            r"([一-龥A-Za-z0-9\- ]{2,40}?)能不能",
            r"([A-Za-z0-9\- ]{2,40}?)(?: side effects| dosage| warnings| indications| contraindications)",
        ]
        # 按顺序尝试匹配药名模式。
        for pattern in patterns:
            # 在问题中搜索首个候选药名。
            match = re.search(pattern, cleaned, flags=re.IGNORECASE)
            # 若匹配成功，则返回清理后的药名。
            if match:
                return self._normalize_candidate(match.group(1))
        # 若末尾包含“药”字，则尝试直接取前一段文本作为药名。
        fallback = re.search(r"([一-龥A-Za-z0-9\- ]{2,40}?药)", cleaned)
        # 若回退匹配成功，则返回该药名。
        if fallback:
            return self._normalize_candidate(fallback.group(1))
        # 若仍未识别成功，则返回空字符串。
        return ""

    # 将抽取出的药名归一化为更适合公开接口的查询词。
    def normalize_drug_name(self, drug_name: str) -> str:
        # 优先从中文别名映射表中查找标准英文名。
        return DRUG_ALIAS_MAP.get(drug_name, drug_name)

    # 依次按品牌名、通用名和成分名检索药品标签。
    def _search_record(self, drug_name: str) -> dict[str, object] | None:
        # 定义 openFDA 可尝试的查询字段列表。
        fields = ["openfda.brand_name", "openfda.generic_name", "openfda.substance_name"]
        # 遍历字段并逐个尝试搜索。
        for field in fields:
            # 尝试请求药品标签接口。
            try:
                # 按当前字段执行单字段精确搜索。
                data = self.http_client.get_json(
                    "https://api.fda.gov/drug/label.json",
                    {
                        "search": f'{field}:"{drug_name}"',
                        "limit": 1,
                    },
                )
            # 若当前字段查询失败，则继续尝试下一个字段。
            except Exception:
                continue
            # 读取查询结果数组。
            results = data.get("results", [])
            # 若查到结果，则直接返回首条记录。
            if results:
                return results[0]
        # 当所有字段都未命中时返回空值。
        return None

    # 将药品标签记录格式化为精简可读摘要。
    def _format_record(self, drug_name: str, record: dict[str, object]) -> str:
        # 提取 openFDA 品牌名列表。
        brand_names = self._take_first_list_value(record.get("openfda", {}), "brand_name")
        # 提取 openFDA 通用名列表。
        generic_names = self._take_first_list_value(record.get("openfda", {}), "generic_name")
        # 提取适应症文本。
        indications = self._take_first_text(record, "indications_and_usage")
        # 提取用法用量文本。
        dosage = self._take_first_text(record, "dosage_and_administration")
        # 提取警示信息文本。
        warnings = self._take_first_text(record, "warnings")
        # 提取不良反应文本。
        adverse = self._take_first_text(record, "adverse_reactions")
        # 准备输出文本行列表。
        lines = [f"药品查询：{drug_name}"]
        # 若存在品牌名，则写入结果。
        if brand_names:
            lines.append(f"品牌名：{brand_names}")
        # 若存在通用名，则写入结果。
        if generic_names:
            lines.append(f"通用名：{generic_names}")
        # 若存在适应症，则写入结果。
        if indications:
            lines.append(f"适应症：{indications}")
        # 若存在用法用量，则写入结果。
        if dosage:
            lines.append(f"用法用量：{dosage}")
        # 若存在警示信息，则写入结果。
        if warnings:
            lines.append(f"警示：{warnings}")
        # 若存在不良反应，则写入结果。
        if adverse:
            lines.append(f"不良反应：{adverse}")
        # 若关键信息全部缺失，则补充统一说明。
        if len(lines) == 1:
            lines.append("接口返回了记录，但缺少适合展示的简要字段。")
        # 返回拼接后的药品摘要文本。
        return "\n".join(lines)

    # 从记录字段中提取首段文本并裁剪长度。
    def _take_first_text(self, record: dict[str, object], field: str) -> str:
        # 读取目标字段的列表值。
        values = record.get(field, [])
        # 若字段为空，则返回空字符串。
        if not values:
            return ""
        # 提取首段文本并压缩空白字符。
        text = re.sub(r"\s+", " ", str(values[0])).strip()
        # 返回裁剪后的摘要，避免单条结果过长。
        return text[:180]

    # 从 openFDA 列表字段中提取首个值。
    def _take_first_list_value(self, record: dict[str, object], field: str) -> str:
        # 读取目标字段值列表。
        values = record.get(field, []) if isinstance(record, dict) else []
        # 若列表为空，则返回空字符串。
        if not values:
            return ""
        # 返回首个列表元素文本。
        return str(values[0]).strip()

    # 移除问题开头的提问前缀，保留更纯净的药品语义。
    def _strip_prefixes(self, text: str) -> str:
        # 在前缀命中时循环剥离，直到没有前缀为止。
        while True:
            # 记录本轮是否执行了剥离操作。
            stripped = False
            # 遍历全部常见前缀。
            for prefix in HELPER_PREFIXES:
                # 若文本以当前前缀开头，则移除该前缀。
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    stripped = True
                    break
            # 若本轮没有继续剥离，则结束循环。
            if not stripped:
                return text

    # 清理药名候选词前缀，避免把提问词一并当作药名。
    def _normalize_candidate(self, candidate: str) -> str:
        # 先清理首尾空白字符。
        normalized = candidate.strip()
        # 若候选词以辅助前缀开头，则继续剥离噪声。
        normalized = self._strip_prefixes(normalized)
        # 返回最终标准化后的药品名称。
        return normalized
