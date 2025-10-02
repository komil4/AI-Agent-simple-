# AI Chat with MCP Integration

Веб-приложение на Python с FastAPI для чата с AI, интегрированное с MCP (Model Context Protocol) серверами для работы с GitLab, Jira, Confluence и Active Directory.

## Возможности

- 💬 Веб-интерфейс чата с AI
- 🤖 Интеграция с OpenAI LLM
- 🔌 Поддержка MCP серверов:
  - GitLab (проекты, задачи)
  - Atlassian (объединенный сервер для Jira, Confluence)
  - Active Directory (пользователи, группы)
- ⚡ Real-time общение через WebSocket
- 📱 Адаптивный дизайн

## Структура проекта

```
├── main.py              # Основное FastAPI приложение
├── config.py            # Управление конфигурацией
├── llm_service.py       # Сервис для работы с LLM
├── mcp_client.py        # Клиент для MCP серверов
├── config.json          # Файл конфигурации
├── requirements.txt     # Зависимости Python
├── templates/
│   └── chat.html       # HTML шаблон чата
└── README.md           # Документация
```

## Установка и настройка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Отредактируйте файл `config.json`:

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "your-openai-api-key-here",
    "model": "gpt-3.5-turbo",
    "base_url": "https://api.openai.com/v1",
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "mcp_servers": {
    "gitlab": {
      "enabled": true,
      "host": "localhost",
      "port": 3001,
      "token": "your-gitlab-token-here",
      "url": "https://gitlab.example.com"
    },
    "atlassian": {
      "enabled": true,
      "host": "localhost",
      "port": 3002,
      "jira_api_token": "your-jira-api-token-here",
      "jira_personal_token": "your-jira-personal-token-here",
      "jira_username": "your-jira-username@example.com",
      "jira_url": "https://your-jira-domain.atlassian.net",
      "confluence_api_token": "your-confluence-api-token-here",
      "confluence_username": "your-confluence-username@example.com",
      "confluence_url": "https://your-confluence-domain.atlassian.net/",
      "confluence_personal_token": "your-confluence-personal-token-here"
    },
    "activedirectory": {
      "enabled": true,
      "host": "localhost",
      "port": 3003,
      "domain": "your-domain.com",
      "username": "your-ad-username",
      "password": "your-ad-password"
    }
  },
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": true
  }
}
```

### 3. Получение API токенов

#### GitLab API Token
1. Войдите в GitLab
2. Перейдите в Settings → Access Tokens
3. Создайте новый токен с правами: `api`, `read_api`, `read_repository`

#### Atlassian API Token (для Jira и Confluence)
1. Войдите в Atlassian Account
2. Перейдите в Security → API tokens
3. Создайте новый API токен
4. Используйте email и API токен для аутентификации

### 4. Настройка MCP серверов

MCP серверы должны быть развернуты в Docker контейнерах и доступны по указанным в конфигурации адресам и портам.

Пример Docker Compose для MCP серверов:

```yaml
version: '3.8'
services:
  # GitLab MCP Server
  gitlab-mcp:
    image: ghcr.io/nguyenvanduocit/gitlab-mcp:latest
    ports:
      - "3001:3000"
    environment:
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - GITLAB_URL=${GITLAB_URL}
  
  # Atlassian MCP Server (объединенный для Jira, Confluence)
  atlassian-mcp:
    image: atlassian-mcp-server:latest
    ports:
      - "3002:3000"
    environment:
      - JIRA_API_TOKEN=${JIRA_API_TOKEN}
      - JIRA_PERSONAL_TOKEN=${JIRA_PERSONAL_TOKEN}
      - JIRA_USERNAME=${JIRA_USERNAME}
      - JIRA_URL=${JIRA_URL}
      - CONFLUENCE_API_TOKEN=${CONFLUENCE_API_TOKEN}
      - CONFLUENCE_USERNAME=${CONFLUENCE_USERNAME}
      - CONFLUENCE_URL=${CONFLUENCE_URL}
      - CONFLUENCE_PERSONAL_TOKEN=${CONFLUENCE_PERSONAL_TOKEN}
  
  activedirectory-mcp:
    image: your-ad-mcp-image
    ports:
      - "3003:3000"
    environment:
      - AD_DOMAIN=${AD_DOMAIN}
      - AD_USERNAME=${AD_USERNAME}
      - AD_PASSWORD=${AD_PASSWORD}
```

## Запуск

### Запуск приложения

```bash
python main.py
```

Или через uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Доступ к приложению

Откройте браузер и перейдите по адресу: http://localhost:8000

## API Endpoints

- `GET /` - Главная страница чата
- `POST /api/chat` - Отправка сообщения
- `GET /api/chat/history` - История чата
- `GET /api/mcp/status` - Статус MCP серверов
- `GET /api/config` - Конфигурация (без секретов)
- `WebSocket /ws` - Real-time чат

## Использование

1. Откройте веб-интерфейс в браузере
2. Введите сообщение в поле ввода
3. AI ассистент автоматически определит, нужны ли данные из MCP серверов
4. Получите ответ с учетом данных из подключенных систем

### Примеры запросов

- "Покажи проекты из GitLab"
- "Какие задачи есть в Jira?"
- "Найди документацию в Confluence"
- "Покажи пользователей из Active Directory"

## Безопасность

- Не храните секретные данные в открытом виде в config.json
- Используйте переменные окружения для чувствительной информации
- Настройте HTTPS для продакшн среды
- Ограничьте доступ к MCP серверам через файрвол

## Разработка

### Структура кода

- `main.py` - FastAPI приложение с маршрутами и WebSocket
- `config.py` - Управление конфигурацией из JSON файла
- `llm_service.py` - Интеграция с OpenAI и обработка MCP контекста
- `mcp_client.py` - Клиенты для различных MCP серверов

### Добавление новых MCP серверов

1. Создайте новый класс в `mcp_client.py`, наследующий от `MCPServer`
2. Добавьте конфигурацию в `config.json`
3. Обновите `MCPManager` для поддержки нового сервера
4. Добавьте соответствующие команды в `LLMService`

## Устранение неполадок

### MCP серверы недоступны

1. Проверьте, что Docker контейнеры запущены
2. Убедитесь, что порты не заняты другими приложениями
3. Проверьте настройки сети и файрвола

### Ошибки LLM

1. Проверьте правильность API ключа OpenAI
2. Убедитесь, что у вас есть доступ к указанной модели
3. Проверьте лимиты API

### Проблемы с веб-интерфейсом

1. Проверьте консоль браузера на ошибки JavaScript
2. Убедитесь, что все статические файлы загружаются
3. Проверьте WebSocket соединение

## Лицензия

MIT License
