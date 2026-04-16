import json
import logging
from urllib.parse import urljoin
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from browser_utils import (
    fetch_page_markdown,
    add_comment_action,
    change_status_action,
    log_time_action,
    create_task_action,
    delete_comment_action,
    edit_description_action
)

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

@mcp.tool()
async def tms_add_comment(issue_url_path: str, comment: str) -> str:
    """
    Adds a COMMENT (Bình luận) to a specific issue. 
    Use this tool ONLY when the user explicitly asks to add a "comment" or "bình luận" or leave a message. 
    Do NOT use this tool if the user asks to update the "description" or "mô tả" (use tms_edit_description instead).
    Args:
        issue_url_path: The relative or absolute path of the specific Issue DETAIL page (e.g., '/tms_pm/Issue/Detail/12345'). Important: Do NOT pass a list view URL.
        comment: The text content of the comment to add.
    """
    base_url = CONFIG.get("base_url")
    full_url = issue_url_path if issue_url_path.startswith("http") else urljoin(base_url, issue_url_path)
    return await add_comment_action(full_url, base_url, comment)

@mcp.tool()
async def tms_change_status(issue_url_path: str, status: str) -> str:
    """
    Changes the status of a specific issue.
    Args:
        issue_url_path: The relative or absolute path of the specific Issue DETAIL page (e.g., '/tms_pm/Issue/Detail/12345'). Do NOT pass a list view URL.
        status: The exact name of the status button to click (e.g., 'In Progress', 'Resolved', 'Closed').
    """
    base_url = CONFIG.get("base_url")
    full_url = issue_url_path if issue_url_path.startswith("http") else urljoin(base_url, issue_url_path)
    return await change_status_action(full_url, base_url, status)

@mcp.tool()
async def tms_log_time(issue_url_path: str, hours: float, work_notes: str, date: str = None) -> str:
    """
    Logs time spent on a specific issue.
    Args:
        issue_url_path: The relative or absolute path of the specific Issue DETAIL page. Do NOT pass a list view URL.
        hours: Number of hours to log.
        work_notes: Description of the work done.
        date: Optional date to log the work (format expected by your system, usually DD/MM/YYYY). Defaults to today if omitted.
    """
    base_url = CONFIG.get("base_url")
    full_url = issue_url_path if issue_url_path.startswith("http") else urljoin(base_url, issue_url_path)
    return await log_time_action(full_url, base_url, hours, work_notes, date)

@mcp.tool()
async def tms_create_task(project_url_path: str, title: str, description: str = "") -> str:
    """
    Creates a new task in a specific project.
    Args:
        project_url_path: The relative or absolute path of the project list or sprint list where the 'New ...' button is present.
        title: Title of the new task.
        description: Optional description for the task.
    """
    base_url = CONFIG.get("base_url")
    full_url = project_url_path if project_url_path.startswith("http") else urljoin(base_url, project_url_path)
    return await create_task_action(full_url, base_url, title, description)

@mcp.tool()
async def tms_delete_comment(issue_url_path: str) -> str:
    """
    Deletes your latest comment on a specific issue.
    Args:
        issue_url_path: The relative or absolute path of the specific Issue DETAIL page. Do NOT pass a list view URL.
    """
    base_url = CONFIG.get("base_url")
    full_url = issue_url_path if issue_url_path.startswith("http") else urljoin(base_url, issue_url_path)
    return await delete_comment_action(full_url, base_url)

@mcp.tool()
async def tms_edit_description(issue_url_path: str, description: str) -> str:
    """
    Edits the MAIN DESCRIPTION (Mô tả) of an existing issue. 
    Use this tool ONLY when the user asks to add or change the "description" or "mô tả" of a task.
    Do NOT use this tool for comments.
    Args:
        issue_url_path: The relative or absolute path of the specific Issue DETAIL page. Do NOT pass a list view URL.
        description: The new text content for the description.
    """
    base_url = CONFIG.get("base_url")
    full_url = issue_url_path if issue_url_path.startswith("http") else urljoin(base_url, issue_url_path)
    return await edit_description_action(full_url, base_url, description)

if __name__ == "__main__":
    mcp.run()
