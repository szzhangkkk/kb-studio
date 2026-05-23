"""Pre-configured LLM provider templates."""

PROVIDER_TEMPLATES: dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "docs_url": "https://platform.deepseek.com/api-keys",
        "features": ["chat", "stream", "function_calling"],
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo"],
        "docs_url": "https://dashscope.console.aliyun.com/",
        "features": ["chat", "stream", "function_calling"],
    },
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4-flash", "glm-4-long"],
        "docs_url": "https://open.bigmodel.cn/",
        "features": ["chat", "stream", "function_calling"],
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
        "docs_url": "https://platform.moonshot.cn/",
        "features": ["chat", "stream", "function_calling"],
    },
    "claude": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7"],
        "docs_url": "https://console.anthropic.com/",
        "features": ["chat", "stream", "tool_use"],
        "adapter": "anthropic",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "docs_url": "https://platform.openai.com/api-keys",
        "features": ["chat", "stream", "function_calling"],
    },
    "ollama": {
        "name": "Ollama (本地)",
        "base_url": "http://localhost:11434/v1",
        "models": ["qwen2.5:7b", "llama3.1", "deepseek-r1:7b", "glm4:9b"],
        "docs_url": "https://ollama.com/",
        "features": ["chat", "stream"],
    },
    "custom": {
        "name": "自定义 (OpenAI 兼容)",
        "base_url": "",
        "models": [],
        "features": ["chat", "stream"],
    },
}


def get_provider_template(provider: str) -> dict:
    return PROVIDER_TEMPLATES.get(provider, PROVIDER_TEMPLATES["custom"])


def list_providers() -> list[dict]:
    return [
        {"id": k, **v}
        for k, v in PROVIDER_TEMPLATES.items()
        if k != "custom"
    ]
