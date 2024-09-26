"""
title: DeepLX Translate
author: mpopui
author_urls: https://github.com/mpopui
description: |
    Use DeepLX translation API to translate the user's native language into the large model's native language, and then translate it back into the user's native language.
version: 1.0
licence: MIT
"""

import re
from typing import List, Optional
from pydantic import BaseModel
import requests
import logging

from open_webui.utils.misc import get_last_user_message, get_last_assistant_message

# 配置日志记录
logging.basicConfig(level=logging.WARNING)  # 设置所需的日志级别


class Filter:
    class Valves(BaseModel):
        api_url: str = (
            "https://deeplx.mingming.dev/translate"  # DeepLX API的URL
        )
        source_user: str = "auto"  # 用户输入的源语言，默认值为"auto"
        target_user: str = "en"  # 用户输入的目标语言，默认值为"en"
        source_assistant: str = "en"  # 助手输入的源语言，默认值为"en"
        target_assistant: str = "zh"  # 助手输入的目标语言，默认值为"zh"

    def __init__(self, valves: Optional[Valves] = None) -> None:
        self.valves = valves if valves else self.Valves()
        self.code_blocks = []  # 存储代码块的列表

    def translate(self, text: str, source: str, target: str) -> str:
        # 更新API URL为DeepLX的URL
        url = self.valves.api_url

        # 构建请求数据
        payload = {"text": text, "source_lang": source, "target_lang": target}
        headers = {
            "Content-Type": "application/json"
        }

        try:
            # 使用POST方法发送请求
            r = requests.post(
                url, json=payload, headers=headers, timeout=10
            )  # 添加超时以提高健壮性
            r.raise_for_status()
            result = r.json()
            translated_text = result["data"]  # 提取翻译后的文本
            return translated_text
        except requests.exceptions.RequestException as e:
            error_msg = f"翻译API错误: {str(e)}"
            logging.error(error_msg)
            return f"{text}\\\\n\\\\n[翻译失败: {error_msg}]"
        except Exception as e:
            error_msg = f"翻译过程中发生意外错误: {str(e)}"
            logging.exception(error_msg)  # 记录意外错误的回溯
            return f"{text}\\\\n\\\\n[翻译失败: {error_msg}]"

    def split_text_around_table(self, text: str) -> List[str]:
        # 使用正则表达式将文本拆分为表格前的文本和表格文本
        table_regex = r"((?:^.*?\\|.*?\\n)+)(?=\\n[^\\|\\s].*?\\|)"
        matches = re.split(table_regex, text, flags=re.MULTILINE)

        if len(matches) > 1:
            return [matches[0], matches[1]]
        else:
            return [text, ""]

    def clean_table_delimiters(self, text: str) -> str:
        # 用单个短划线替换表格分隔符周围的多个空格
        return re.sub(r"(\\|\\s*-+\\s*)+", lambda m: m.group(0).replace(" ", "-"), text)

    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        print(f"入口函数: {__name__}")
        print(f"用户输入的源语言: {self.valves.source_user}")
        print(f"用户输入的目标语言: {self.valves.target_user}")
        print(f"助手输入的源语言: {self.valves.source_assistant}")
        print(f"助手输入的目标语言: {self.valves.target_assistant}")

        user_message = get_last_user_message(body["messages"])

        # 查找并存储代码块
        code_regex = r"```(.*?)```"
        self.code_blocks = re.findall(code_regex, user_message, flags=re.DOTALL)

        # 暂时用占位符替换代码块
        user_message_processed = re.sub(
            code_regex, "__CODE_BLOCK__", user_message, flags=re.DOTALL
        )

        if self.valves.source_user != self.valves.target_user:
            parts = self.split_text_around_table(user_message_processed)
            text_before_table, table_text = parts

            translated_before_table = self.translate(
                text_before_table,
                self.valves.source_user,
                self.valves.target_user,
            )

            translated_user_message = translated_before_table + table_text
            translated_user_message = self.clean_table_delimiters(
                translated_user_message
            )

            # 在翻译后的消息中还原代码块
            for code in self.code_blocks:
                translated_user_message = translated_user_message.replace(
                    "__CODE_BLOCK__", f"```{code}```", 1
                )

            for message in reversed(body["messages"]):
                if message["role"] == "user":
                    if "[翻译失败:" in translated_user_message:
                        print(
                            f"翻译失败，语言对为 {self.valves.source_user} 到 {self.valves.target_user}"
                        )
                    else:
                        message["content"] = translated_user_message
                    break

        return body

    async def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        print(f"出口函数: {__name__}")
        print(f"用户输入的源语言: {self.valves.source_user}")
        print(f"用户输入的目标语言: {self.valves.target_user}")
        print(f"助手输入的源语言: {self.valves.source_assistant}")
        print(f"助手输入的目标语言: {self.valves.target_assistant}")

        assistant_message = get_last_assistant_message(body["messages"])

        # 查找并存储代码块
        code_regex = r"```(.*?)```"
        self.code_blocks = re.findall(code_regex, assistant_message, flags=re.DOTALL)

        # 暂时用占位符替换代码块
        assistant_message_processed = re.sub(
            code_regex, "__CODE_BLOCK__", assistant_message, flags=re.DOTALL
        )

        if self.valves.source_assistant != self.valves.target_assistant:
            parts = self.split_text_around_table(assistant_message_processed)
            text_before_table, table_text = parts

            translated_before_table = self.translate(
                text_before_table,
                self.valves.source_assistant,
                self.valves.target_assistant,
            )

            translated_assistant_message = translated_before_table + table_text
            translated_assistant_message = self.clean_table_delimiters(
                translated_assistant_message
            )

            # 在翻译后的消息中还原代码块
            for code in self.code_blocks:
                translated_assistant_message = translated_assistant_message.replace(
                    "__CODE_BLOCK__", f"```{code}```", 1
                )

            for message in reversed(body["messages"]):
                if message["role"] == "assistant":
                    if "[翻译失败:" in translated_assistant_message:
                        print(
                            f"翻译失败，语言对为 {self.valves.source_assistant} 到 {self.valves.target_assistant}"
                        )
                    else:
                        message["content"] = translated_assistant_message
                    break

        return body
