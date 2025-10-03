import asyncio
import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from config import config
from mcp_client import mcp_manager

class LLMService:
    """Сервис для работы с LLM"""
    
    def __init__(self):
        self.llm_config = config.get_llm_config()
        self.client = AsyncOpenAI(
            api_key=self.llm_config.get("api_key"),
            base_url=self.llm_config.get("base_url")
        )
        self.model = self.llm_config.get("model", "gpt-3.5-turbo")
        self.temperature = self.llm_config.get("temperature", 0.7)
        self.max_tokens = self.llm_config.get("max_tokens", 1000)
    
    async def generate_response(self, messages: List[Dict[str, str]], mcp_context: Optional[Dict] = None) -> str:
        """Генерирует ответ от LLM с учетом контекста MCP"""
        
        # Добавляем системное сообщение с информацией о доступных MCP серверах
        system_message = self._create_system_message(mcp_context)
        
        # Формируем сообщения для LLM
        llm_messages = [{"role": "system", "content": system_message}] + messages
        
        # Подготавливаем инструменты для OpenAI API
        tools = []
        if mcp_context and "available_tools" in mcp_context:
            for server_name, server_tools in mcp_context["available_tools"].items():
                for tool in server_tools:
                    # Преобразуем инструмент MCP в формат OpenAI
                    openai_tool = {
                        "type": "function",
                        "function": {
                            "name": f"{server_name}_{getattr(tool, 'name', 'unknown')}",
                            "description": getattr(tool, 'description', ''),
                            "parameters": getattr(tool, 'inputSchema', {})
                        }
                    }
                    tools.append(openai_tool)
        
        try:
            # Формируем параметры для API
            api_params = {
                "model": self.model,
                "messages": llm_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
            
            # Добавляем инструменты, если они есть
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**api_params)
            
            message = response.choices[0].message
            
            # Если LLM хочет вызвать инструмент
            if message.tool_calls:
                # Выполняем вызовы инструментов
                tool_results = []
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    # Парсим имя сервера и инструмента
                    if '_' in tool_name:
                        server_name, actual_tool_name = tool_name.split('_', 1)
                        result = await mcp_manager.call_tool(server_name, actual_tool_name, tool_args)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "result": result
                        })
                
                # Добавляем результаты инструментов в контекст
                llm_messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                # Добавляем результаты инструментов
                for tool_result in tool_results:
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "name": tool_result["name"],
                        "content": json.dumps(tool_result["result"], ensure_ascii=False)
                    })
                
                # Получаем финальный ответ
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=llm_messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
                return final_response.choices[0].message.content

            # Иногда LLM возвращает не tool call, а json-строку с вызовом инструмента
            # Пример: ["gitlab_gitlab_search(action='global', query='ONEC-8927', scope='issues')"]
            try:
                content = message.content
                # Проверяем, является ли content JSON-массивом с вызовами
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    tool_results = []
                    for call_str in parsed:
                        # Пример строки: "gitlab_gitlab_search(action='global', query='ONEC-8927', scope='issues')"
                        # Парсим имя инструмента и аргументы
                        if '(' in call_str and call_str.endswith(')'):
                            tool_name, args_str = call_str.split('(', 1)
                            args_str = args_str[:-1]  # remove trailing ')'
                            # Преобразуем строку аргументов в словарь
                            # Преобразуем аргументы вида: action='global', query='ONEC-8927', scope='issues'
                            args = {}
                            for arg in args_str.split(','):
                                if '=' in arg:
                                    k, v = arg.split('=', 1)
                                    k = k.strip()
                                    v = v.strip().strip("'").strip('"')
                                    args[k] = v
                            if '_' in tool_name:
                                server_name, actual_tool_name = tool_name.split('_', 1)
                                result = await mcp_manager.call_tool(server_name, actual_tool_name, args)
                                tool_results.append({
                                    "tool_call_id": None,
                                    "name": tool_name,
                                    "result": result
                                })
                    # Добавляем результаты инструментов в контекст
                    llm_messages.append({
                        "role": "assistant",
                        "content": message.content
                    })
                    for tool_result in tool_results:
                        llm_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_result["tool_call_id"],
                            "name": tool_result["name"],
                            "content": json.dumps(tool_result["result"], ensure_ascii=False)
                        })
                    # Получаем финальный ответ
                    final_response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=llm_messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )
                    return final_response.choices[0].message.content
            except Exception:
                pass  # Если не удалось распарсить как json, просто возвращаем content

            return message.content
            
            return message.content
        except Exception as e:
            return f"Ошибка при обращении к LLM: {str(e)}"
    
    def _create_system_message(self, mcp_context: Optional[Dict] = None) -> str:
        """Создает системное сообщение с информацией о доступных MCP серверах"""
        system_prompt = """Вы - полезный AI ассистент, который может работать с различными системами через MCP (Model Context Protocol) серверы.

Вы можете использовать доступные инструменты для получения актуальной информации из различных систем.

Отвечайте на русском языке, если пользователь пишет на русском."""
        
        return system_prompt
    
    async def process_message_with_mcp(self, user_message: str) -> Dict[str, Any]:
        """Обрабатывает сообщение пользователя с использованием MCP серверов"""
        
        # Проверяем доступные MCP серверы
        available_servers = await mcp_manager.get_available_servers()
        
        # Получаем информацию о всех доступных инструментах
        all_tools = await mcp_manager.get_all_tools()
        
        # Формируем контекст для LLM
        mcp_context = {
            "available_servers": available_servers,
            "available_tools": all_tools,
            "tools_summary": self._create_tools_summary(all_tools)
        }
        
        # Генерируем ответ от LLM (теперь LLM сам выбирает инструменты через OpenAI Tools API)
        messages = [{"role": "user", "content": user_message}]
        llm_response = await self.generate_response(messages, mcp_context)
        
        return {
            "response": llm_response,
            "mcp_context": mcp_context,
            "available_servers": available_servers
        }
    
    
    def _create_tools_summary(self, all_tools: Dict[str, List[Dict]]) -> str:
        """Создает краткое описание доступных инструментов"""
        summary = "Доступные MCP инструменты:\n"
        
        for server_name, tools in all_tools.items():
            summary += f"\n{server_name}:\n"
            for tool in tools:
                name = getattr(tool, "name", "")
                description = getattr(tool, "description", "")
                summary += f"  - {name}: {description}\n"
        
        return summary
    

# Глобальный экземпляр сервиса LLM
llm_service = LLMService()
