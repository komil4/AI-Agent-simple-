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
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=llm_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка при обращении к LLM: {str(e)}"
    
    def _create_system_message(self, mcp_context: Optional[Dict] = None) -> str:
        """Создает системное сообщение с информацией о доступных MCP серверах"""
        system_prompt = """Вы - полезный AI ассистент, который может работать с различными системами через MCP (Model Context Protocol) серверы.

Вы можете использовать доступные MCP инструменты для получения информации из внешних систем. Информация о доступных серверах и инструментах будет предоставлена в контексте.

Отвечайте на русском языке, если пользователь пишет на русском."""
        
        if mcp_context:
            system_prompt += f"\n\nКонтекст MCP серверов: {json.dumps(mcp_context, ensure_ascii=False)}"
        
        return system_prompt
    
    async def process_message_with_mcp(self, user_message: str) -> Dict[str, Any]:
        """Обрабатывает сообщение пользователя с использованием MCP серверов"""
        
        # Проверяем доступные MCP серверы
        available_servers = await mcp_manager.get_available_servers()
        
        # Получаем информацию о всех доступных инструментах
        all_tools = await mcp_manager.get_all_tools()
        
        # Получаем информацию о серверах
        server_info = {}
        for server_name in available_servers:
            info = await mcp_manager.get_server_info(server_name)
            server_info[server_name] = info
        
        # Анализируем сообщение на предмет запросов к MCP серверам
        mcp_requests = await self._analyze_message_with_llm(user_message, all_tools)
        
        mcp_results = {}
        
        # Выполняем запросы к MCP серверам
        for server_name, tool_name, params in mcp_requests:
            if server_name in available_servers:
                result = await mcp_manager.call_tool(server_name, tool_name, params)
                mcp_results[f"{server_name}_{tool_name}"] = result
        
        # Формируем контекст для LLM
        mcp_context = {
            "available_servers": available_servers,
            "server_info": server_info,
            "available_tools": all_tools,
            "tools_summary": self._create_tools_summary(all_tools),
            "mcp_results": mcp_results
        }
        
        # Генерируем ответ от LLM
        messages = [{"role": "user", "content": user_message}]
        llm_response = await self.generate_response(messages, mcp_context)
        
        return {
            "response": llm_response,
            "mcp_context": mcp_context,
            "available_servers": available_servers
        }
    
    def _analyze_message_for_mcp_requests(self, message: str, available_tools: Dict[str, List[Dict]]) -> List[tuple]:
        """Анализирует сообщение и определяет необходимые запросы к MCP серверам"""
        requests = []
        message_lower = message.lower()
        
        # Простой анализ ключевых слов для определения нужных MCP запросов
        # Теперь используем динамически полученные инструменты
        
        # Ищем подходящие инструменты на основе ключевых слов
        for server_name, tools in available_tools.items():
            for tool in tools:
                tool_name = tool.get("name", "")
                tool_description = tool.get("description", "").lower()
                
                # Проверяем соответствие ключевых слов описанию инструмента
                if any(word in message_lower for word in ["gitlab", "git", "проект", "репозиторий"]):
                    if any(keyword in tool_description for keyword in ["project", "repository", "git"]):
                        requests.append((server_name, tool_name, {}))
                
                elif any(word in message_lower for word in ["jira", "задача", "тикет", "баг"]):
                    if any(keyword in tool_description for keyword in ["issue", "task", "bug", "jira"]):
                        requests.append((server_name, tool_name, {}))
                
                elif any(word in message_lower for word in ["confluence", "документ", "страница", "wiki"]):
                    if any(keyword in tool_description for keyword in ["page", "document", "space", "confluence"]):
                        requests.append((server_name, tool_name, {}))
                
                elif any(word in message_lower for word in ["пользователь", "группа", "ad", "active directory"]):
                    if any(keyword in tool_description for keyword in ["user", "group", "directory", "ad"]):
                        requests.append((server_name, tool_name, {}))
        
        # Убираем дубликаты
        unique_requests = list(set(requests))
        return unique_requests
    
    def _create_tools_summary(self, all_tools: Dict[str, List[Dict]]) -> str:
        """Создает краткое описание доступных инструментов"""
        summary = "Доступные MCP инструменты:\n"
        
        for server_name, tools in all_tools.items():
            summary += f"\n{server_name}:\n"
            for tool in tools:
                name = tool.get("name", "")
                description = tool.get("description", "")
                summary += f"  - {name}: {description}\n"
        
        return summary
    
    async def _analyze_message_with_llm(self, message: str, available_tools: Dict[str, List[Dict]]) -> List[tuple]:
        """Использует LLM для анализа сообщения и определения нужных инструментов"""
        try:
            # Формируем промпт для анализа
            tools_description = ""
            for server_name, tools in available_tools.items():
                tools_description += f"\n{server_name}:\n"
                for tool in tools:
                    tools_description += f"  - {tool.get('name', '')}: {tool.get('description', '')}\n"
            
            analysis_prompt = f"""Проанализируй сообщение пользователя и определи, какие MCP инструменты нужно вызвать.

Сообщение пользователя: "{message}"

Доступные инструменты:
{tools_description}

Верни только JSON массив с объектами вида:
[{{"server": "имя_сервера", "tool": "имя_инструмента", "arguments": {{}}}}]

Если инструменты не нужны, верни пустой массив [].

Пример:
[{{"server": "gitlab", "tool": "list_projects", "arguments": {{}}}}]"""

            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.generate_response(messages)
            
            # Парсим JSON ответ
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                tools_to_call = json.loads(json_str)
                
                # Преобразуем в формат tuple
                requests = []
                for tool_call in tools_to_call:
                    requests.append((
                        tool_call.get("server"),
                        tool_call.get("tool"),
                        tool_call.get("arguments", {})
                    ))
                return requests
            
        except Exception as e:
            print(f"Ошибка анализа с LLM: {e}")
        
        # Fallback к простому анализу
        return self._analyze_message_for_mcp_requests(message, available_tools)

# Глобальный экземпляр сервиса LLM
llm_service = LLMService()
