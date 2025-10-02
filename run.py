#!/usr/bin/env python3
"""
Скрипт запуска AI Chat с MCP интеграцией
"""

import uvicorn
from config import config

if __name__ == "__main__":
    server_config = config.get_server_config()
    
    print("🚀 Запуск AI Chat с MCP интеграцией...")
    print(f"📡 Сервер: {server_config.get('host', '0.0.0.0')}:{server_config.get('port', 8000)}")
    print(f"🔧 Режим отладки: {'Включен' if server_config.get('debug', True) else 'Выключен'}")
    print("🌐 Откройте браузер: http://localhost:8000")
    print("-" * 50)
    
    uvicorn.run(
        "main:app",
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 8000),
        reload=server_config.get("debug", True),
        log_level="info"
    )
