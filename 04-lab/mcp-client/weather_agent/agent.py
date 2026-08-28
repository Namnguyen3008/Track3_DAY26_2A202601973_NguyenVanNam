"""
Weather Agent - Connects to Remote MCP Server with Model Round-Robin
Supports Round-Robin between Gemini 3.1 Flash Lite and Gemini 3.5 Flash Lite!
"""

from __future__ import annotations

import itertools
import logging
import os
import sys
from dotenv import load_dotenv

# Đảm bảo in tiếng Việt & emoji chuẩn trên Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

# Cấu hình API key từ biến môi trường hoặc file .env
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if API_KEY:
    os.environ["GOOGLE_API_KEY"] = API_KEY
    os.environ["GEMINI_API_KEY"] = API_KEY

from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8085/mcp")

# Danh sách models round-robin
MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]
_model_cycler = itertools.cycle(MODELS)


def round_robin_model_switch(callback_context=None, **kwargs):
    """Callback luân phiên chuyển model trước mỗi lượt chạy của Agent."""
    next_model = next(_model_cycler)
    if "root_agent" in globals() and globals()["root_agent"] is not None:
        globals()["root_agent"].model = next_model
    logger.info(f"🔄 [ADK Round-Robin] Chuyển active model sang: {next_model}")
    return None


logger.info("🌐 Initializing weather agent with remote MCP server")
logger.info(f"📡 MCP Server: {MCP_SERVER_URL}")

try:
    # Create connection parameters for the remote MCP server
    connection_params = StreamableHTTPConnectionParams(
        url=MCP_SERVER_URL,
        timeout=30.0,
    )

    # Create the MCP toolset - this will connect to the server
    logger.info("🔌 Connecting to MCP server...")
    weather_tools = McpToolset(
        connection_params=connection_params,
    )
    logger.info("✅ MCP toolset created successfully")

    # Create the agent with remote MCP tools and round-robin callback
    root_agent = Agent(
        name="weather_agent",
        model=MODELS[0],
        tools=[weather_tools],
        before_agent_callback=round_robin_model_switch,
    )
    logger.info("✅ Weather agent initialized with remote MCP tools:")
    logger.info("   - get_current_weather(city)")
    logger.info("   - get_forecast(city, days)")
    logger.info("   - health_check()")
    logger.info(f"🔄 Round-robin models: {MODELS}")

except Exception as e:
    logger.error(f"❌ Failed to connect to remote MCP server: {e}")
    logger.error(f"   Server URL: {MCP_SERVER_URL}")
    import traceback

    traceback.print_exc()

    # Create a fallback agent without tools
    logger.warning("⚠️  Creating fallback agent without MCP tools")
    root_agent = Agent(
        name="weather_agent",
        model=MODELS[0],
        before_agent_callback=round_robin_model_switch,
    )


