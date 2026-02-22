import aiohttp
import logging
from logger_config import get_logger

logger = get_logger("LanguageUtils")


class AILanguageClient:
    """
    硅基流动AI语言模型客户端，用于处理文本生成、问答等语言相关任务
    使用 deepseek-ai/DeepSeek-V3 模型
    """

    def __init__(self, api_key: str, model: str, base_url: str, timeout_config: dict = None):
        """
        初始化AI语言模型客户端

        :param api_key: 硅基流动API密钥
        :param model: 模型名称
        :param base_url: API基础URL
        :param timeout_config: 超时配置字典 {total: int, connect: int}
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip()  # 修复：去除末尾空格
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        # 保存超时配置，默认为None将使用后续的默认值
        self.timeout_config = timeout_config or {}

    async def generate_text(self, prompt: str, temperature: float = 0.7, max_tokens: int = 512) -> str:
        """
        生成文本内容

        :param prompt: 提示文本
        :param temperature: 生成温度，控制随机性
        :param max_tokens: 最大生成token数
        :return: 生成的文本内容
        """
        # 注意：这个方法没有context参数，无法直接检查全局开关
        # 需要在调用此方法前检查开关状态
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            # 从配置中读取超时时间
            total_timeout = self.timeout_config.get('total', 120)  # 默认总超时120秒
            connect_timeout = self.timeout_config.get('connect', 10)  # 默认连接超时10秒
            timeout = aiohttp.ClientTimeout(total=total_timeout, connect=connect_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()

                    # 增强健壮性：检查响应结构
                    if "choices" not in result or not result["choices"]:
                        logger.error(f"AI响应缺少choices字段: {result}")
                        raise ValueError("Invalid AI response: missing 'choices'")
                    choice = result["choices"][0]
                    if "message" not in choice or "content" not in choice["message"]:
                        logger.error(f"AI响应缺少message/content: {choice}")
                        raise ValueError("Invalid AI response: missing 'message.content'")
                    
                    return choice["message"]["content"].strip()
        except aiohttp.ClientError as e:
            logger.error(f"AI语言模型API调用失败 (网络/HTTP): {str(e)}")
            raise
        except ValueError as e:
            logger.error(f"AI语言模型API返回格式错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"AI语言模型处理失败 (未知错误): {str(e)}")
            raise

    async def select_relevant_items(self, question: str, items: list, item_type: str = "答案") -> list:
        """
        让AI从提供的项目列表中选择与问题相关的项目

        :param question: 用户问题
        :param items: 候选项目列表
        :param item_type: 项目类型描述，如"答案"、"选项"等
        :return: 选中的项目索引列表（0-based）
        """
        if not items:
            return []

        items_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
        prompt = f"""你是一个智慧的助手。
用户提出了一个问题，我从数据库中随机抽出了几个可能的{item_type}，请你判断哪些{item_type}是可用于回应这个问题的，即使模棱两可也好。

问题：{question}

候选{item_type}：
{items_text}

请只返回适合用于回答该问题的{item_type}编号（用英文逗号分隔），不要解释，不要输出其他内容。
例如：1,3,5
"""

        try:
            reply = await self.generate_text(prompt, temperature=0.3)  # 降低温度提高确定性
            # 解析AI返回的编号（转为0-based索引）
            indices = []
            for part in reply.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(items):
                        indices.append(idx)
            return list(set(indices))  # 去重
        except Exception as e:
            logger.error(f"AI选择相关项目失败: {str(e)}")
            return []

    async def generate_explanation(self, answer: str, question: str) -> str:
        """
        为给定的答案和问题生成解释

        :param answer: 答案内容
        :param question: 用户问题
        :return: 生成的解释文本
        """
        prompt = f"""你是一位充满智慧的哲人。
请用一句话解释为什么“{answer}”是对问题“{question}”的一个深刻回应。
要求：
- 只输出解释内容本身
- 不要加"解释："、"——"、引号、序号、Markdown
- 语言简洁、有启发性、带点诗意或禅意
- 不要换行，不要多余空格

示例输入：
问题：我要换工作吗？
答案：听从内心
正确输出：
心之所向，即是归途

现在请为以下内容生成解释：

问题：{question}
答案：{answer}
输出："""

        try:
            raw = await self.generate_text(prompt, temperature=0.85)
            clean = raw.strip()

            # 移除可能的前缀
            prefixes = ["输出：", "解释：", "——", ":", "：", "输出:", "Output:", "Output："]
            for prefix in prefixes:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):].strip()

            # 移除首尾的中英文引号
            quotes = ['"', "'", "“", "”", "‘", "’"]
            while clean and clean[0] in quotes:
                clean = clean[1:]
            while clean and clean[-1] in quotes:
                clean = clean[:-1]

            clean = clean.strip(" 。.,，!！?？\n\t ")

            return clean if clean else "顺其自然，自有答案。"
        except Exception as e:
            logger.error(f"AI生成解释失败: {str(e)}")
            return "顺其自然，自有答案。"


async def get_ai_language_client(config: dict) -> AILanguageClient:
    """
    从配置中获取AI语言客户端实例

    :param config: 配置字典
    :return: AILanguageClient实例
    """
    # 检查全局LLM开关
    if not config.get("llm_enabled", False):
        logger.debug("LLM功能已禁用，无法获取AI语言客户端")
        raise ValueError("LLM功能已禁用")
        
    ai_config = config.get("ai_language", {})
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "deepseek-ai/DeepSeek-V3")
    base_url = ai_config.get("base_url", "https://api.siliconflow.cn/v1/chat/completions")
    timeout_config = ai_config.get("timeout", {})  # 获取超时配置

    if not api_key:
        logger.error("AI语言模型API密钥未配置")
        raise ValueError("AI语言模型API密钥未配置")

    # 确保 base_url 没有尾部空格
    base_url = base_url.strip()
    if not base_url:
        raise ValueError("AI语言模型 base_url 为空")

    return AILanguageClient(api_key, model, base_url, timeout_config)


async def call_ai_language(prompt: str, config: dict, temperature: float = 0.7, max_tokens: int = 512) -> str:
    """
    便捷函数：直接调用AI语言模型生成文本

    :param prompt: 提示文本
    :param config: 配置字典
    :param temperature: 生成温度
    :param max_tokens: 最大生成token数
    :return: 生成的文本内容
    """
    # 检查全局LLM开关
    if not config.get("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过语言模型调用")
        return "顺其自然，自有答案。"
        
    client = await get_ai_language_client(config)
    return await client.generate_text(prompt, temperature, max_tokens)


async def select_relevant_answers(question: str, candidate_answers: list, config: dict) -> list:
    """
    便捷函数：让AI选择与问题相关的答案

    :param question: 用户问题
    :param candidate_answers: 候选答案列表
    :param config: 配置字典
    :return: 选中的答案索引列表
    """
    # 检查全局LLM开关
    if not config.get("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过答案选择")
        return []
        
    client = await get_ai_language_client(config)
    return await client.select_relevant_items(question, candidate_answers, "答案")


async def generate_answer_explanation(answer: str, question: str, config: dict) -> str:
    """
    便捷函数：为答案和问题生成解释

    :param answer: 答案内容
    :param question: 用户问题
    :param config: 配置字典
    :return: 生成的解释文本
    """
    # 检查全局LLM开关
    if not config.get("llm_enabled", False):
        logger.debug("LLM功能已禁用，跳过解释生成")
        return "顺其自然，自有答案。"
        
    client = await get_ai_language_client(config)
    return await client.generate_explanation(answer, question)