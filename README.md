# AI Slack Bot - Production Ready

A modular, production-ready Slack bot powered by OpenRouter AI. Provides intelligent responses, configurable settings, slash commands, and health monitoring.

## How the Bot Works

- **AI Responses:** Uses OpenRouter AI to generate helpful, workplace-appropriate replies when mentioned or messaged (configurable).
- **Configurable Settings:** Users can change bot behavior (reply in thread, mention-only, auto-respond, LLM model) via `/bot-settings` or the App Home tab.
- **Slash Commands:** `/bot-settings`, `/switch-llm`, `/bot-help`, `/bot-debug` for configuration, model switching, help, and debugging.
- **Health Endpoint:** `/health` endpoint for deployment monitoring.

## Project Structure

```
FinalBot/
├── main.py                # Main entry point, all core logic (env, settings, health, AI service, event handlers)
├── bot_settings.json      # Persistent settings storage (auto-created/updated)
├── requirements.txt       # Python dependencies
└── src/
    ├── slash_commands.py  # All slash command logic
    └── llm_models.py      # LLM model config and helpers
```

## File/Module Overview

- **main.py**
  - Loads environment variables and validates tokens
  - Manages persistent settings (`bot_settings.json`)
  - Contains the AI service (OpenRouter integration)
  - Registers event handlers (mentions, DMs, App Home)
  - Starts the health check server
  - Orchestrates the Slack bot lifecycle

- **src/slash_commands.py**
  - Handles all slash commands: `/bot-settings`, `/switch-llm`, `/bot-help`, `/bot-debug`
  - Opens modals for settings and LLM model selection
  - Updates settings via the bot's settings interface

- **src/llm_models.py**
  - Defines available LLM models, display names, and model IDs
  - Provides helpers for Slack dropdowns and display

- **bot_settings.json**
  - Stores user-configurable settings (thread replies, mention-only, auto-respond, LLM model)
  - Updated automatically by slash commands and modals

## Settings & Slash Commands

- **/bot-settings**: Opens a modal to configure reply-in-thread, mention-only, and auto-respond options. Saves to `bot_settings.json`.
- **/switch-llm**: Opens a modal to select the LLM model. Updates the model used for AI responses.
- **/bot-help**: Shows help and usage instructions.
- **/bot-debug**: Shows debug and status info.

## Environment Variables

- `SLACK_BOT_TOKEN` - Bot token (xoxb-...)
- `SLACK_APP_TOKEN` - App token (xapp-...)
- `OPEN_ROUTER_KEY` - OpenRouter API key (sk-or-...)
- `PORT` - Health server port (default: 8080)

## Running the Bot

1. Set environment variables in a `.env` file or your environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the bot:
   ```bash
   python main.py
   ```

## How Settings Work

- Settings are stored in `bot_settings.json` and loaded on startup.
- When a user updates settings via `/bot-settings` or `/switch-llm`, the file is updated immediately.
- The bot reads settings for every relevant event/command, so changes take effect instantly.

## Troubleshooting

- If slash commands do not appear, ensure they are created in your Slack app settings and the `commands` scope is enabled.
- If settings do not update, check bot logs for errors and ensure `bot_settings.json` is writable.
- For more, see the troubleshooting section in this README.

---

For more details, see the comments in each file and the Slack app setup guide below.
