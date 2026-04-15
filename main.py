import json
import logging
from urllib.parse import urljoin
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from browser_utils import fetch_page_markdown

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    logger.warning("config.json not found. Using empty config.")
    CONFIG = {"base_url": "", "views": {}}

# Create FastMCP server
mcp = FastMCP("pm-mcp")

@mcp.tool()
async def list_views() -> str:
    """
    Returns a list of all available task management views that can be read.
    """
    views = list(CONFIG.get("views", {}).keys())
    return f"Available views: {', '.join(views)}"

@mcp.tool()
async def read_view(view_name: str) -> str:
    """
    Reads a predefined view from the task management system and returns its contents in Markdown format.
    Args:
        view_name: The name of the view to read (e.g., 'My Tasks', 'All Projects'). Get available views using list_views().
        
    Name user: HungDM
    """
    views = CONFIG.get("views", {})
    if view_name not in views:
        return f"Error: View '{view_name}' not found. Use list_views() to see available options."
    
    base_url = CONFIG.get("base_url")
    url_path = views[view_name]
    full_url = urljoin(base_url, url_path)
    
    return await fetch_page_markdown(full_url, base_url)

@mcp.tool()
async def read_custom_url(url_path: str) -> str:
    """
    Reads a specific path from the task management system and returns its contents in Markdown.
    Useful when you find a link to a specific task (e.g., /tms_pm/Issue/1234) and want to load it.
    This pm have base_url is https://192.168.66.86:8618
    Args:
        url_path: The relative or absolute path to load (e.g., '/tms_pm/Issue/12345').
    """
    base_url = CONFIG.get("base_url")
    
    if url_path.startswith("http"):
        full_url = url_path
    else:
        full_url = urljoin(base_url, url_path)
        
    return await fetch_page_markdown(full_url, base_url)

if __name__ == "__main__":
    mcp.run()

