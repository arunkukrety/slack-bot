"""LLM Model configuration for the Slack bot."""

LLM_MODELS = {
    "Llama": {
        "display_name": "Llama 3.3 70B",
        "model_id": "meta-llama/llama-3.3-70b-instruct:free",
        "description": "Llama AI model"
    },
    "mistral": {
        "display_name": "Mistral Small 3.2 24B",
        "model_id": "mistralai/mistral-small-3.2-24b-instruct:free",
        "description": "Mistral AI model"
    },
    "deepseek": {
        "display_name": "Gemini Flash 2.0",
        "model_id": "google/gemini-2.0-flash-exp:free",
        "description": "Gemini Flash AI model"
    }
}

def get_model_display_name(model_id: str) -> str:
    """Get display name for a model ID."""
    for key, config in LLM_MODELS.items():
        if config["model_id"] == model_id:
            return config["display_name"]
    return "Unknown Model"

def get_model_options():
    """Get options for Slack dropdown."""
    return [
        {
            "text": {"type": "plain_text", "text": config["display_name"]},
            "value": config["model_id"]
        }
        for config in LLM_MODELS.values()
    ]
