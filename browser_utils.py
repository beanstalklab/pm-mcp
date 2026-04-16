import os
import re
import logging
import asyncio
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright, BrowserContext

logger = logging.getLogger(__name__)

async def setup_browser_context(p, base_url: str) -> BrowserContext:
    """Sets up an incognito browser context with cookies from environment."""
    browser = await p.chromium.launch(headless=True)
    
    # Parse cookie string securely
    cookie_str = os.getenv("SESSION_COOKIE", "")
    cookies = []
    if cookie_str:
        for item in cookie_str.split(';'):
            if '=' in item:
                name, val = item.strip().split('=', 1)
                cookies.append({
                    "name": name,
                    "value": val,
                    "url": base_url
                })
    
    context = await browser.new_context(
        ignore_https_errors=True,
    )
    if cookies:
        await context.add_cookies(cookies)
        
    return context

def extract_tables_as_markdown(html_content: str) -> str:
    """Extracts tables/grids from HTML and converts them to Markdown."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove noise
    for noise in soup(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
        noise.extract()
        
    # Find all table-like structures
    tables = soup.find_all('table')
    grid_divs = soup.find_all('div', role=lambda x: x and x.lower() in ['table', 'grid', 'treegrid'])
    
    # Capture important info panels using robust CSS selectors
    info_panels = []
    selectors = [
        '[id*="issue-quickview-detail" i]',
        '[id*="project-quickview-detail" i]',
        '[id*="project-info" i]',
        '[id*="overview" i]',
        '.card'
    ]
    
    for selector in selectors:
        try:
            info_panels.extend(soup.select(selector))
        except Exception:
            pass # ignore invalid selectors in some bs4 versions
            
    # Deduplicate panels (BeautifulSoup elements)
    unique_panels = {id(p): p for p in info_panels}.values()
    
    target_elements = list(unique_panels) + tables + grid_divs
    
    if not target_elements:
        # Fallback to body text if no tables found
        body = soup.find('body')
        return md(str(body) if body else str(soup), heading_style="ATX", strip=['img'])

    # Convert each found element to markdown
    result_md = ""
    for el in target_elements:
        result_md += md(str(el), heading_style="ATX", strip=['img']) + "\n\n"
        
    return result_md.strip()

async def fetch_page_markdown(url: str, base_url: str) -> str:
    """
    Fetches a URL using Playwright. 
    Detects tabs (nav-tabs), clicks each, and aggregates all table data.
    """
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000) # Wait for initial load
            
            # 1. Identify all tabs
            # Look for common tab patterns: .nav-tabs .nav-link, .nav-item, [role="tab"]
            tab_selectors = [
                ".nav-tabs .nav-link",
                ".nav-tabs .nav-item",
                "[role='tab']",
                ".tab-item"
            ]
            
            tabs = []
            for selector in tab_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    tabs = elements
                    break
            
            final_markdown = ""
            
            if not tabs:
                # No tabs found, just scrape once
                content = await page.content()
                final_markdown = extract_tables_as_markdown(content)
            else:
                # Iterate through tabs
                logger.info(f"Detected {len(tabs)} tabs. Starting multi-tab scrape.")
                for i in range(len(tabs)):
                    try:
                        # Re-query tabs because clicking might detach elements in some SPAs
                        current_tabs = await page.query_selector_all(selector)
                        if i >= len(current_tabs): break
                        
                        target_tab = current_tabs[i]
                        tab_name = await target_tab.inner_text()
                        tab_name = tab_name.strip() or f"Tab {i+1}"
                        
                        logger.info(f"Scraping tab: {tab_name}")
                        
                        # Click tab
                        await target_tab.click()
                        
                        # Wait for potential loading (spinner or idle)
                        await page.wait_for_timeout(1500)
                        
                        # Scrape tab content
                        tab_content = await page.content()
                        tab_md = extract_tables_as_markdown(tab_content)
                        
                        final_markdown += f"## Tab: {tab_name}\n\n{tab_md}\n\n"
                        final_markdown += "---\n\n"
                        
                    except Exception as tab_err:
                        logger.warning(f"Failed to scrape tab {i}: {tab_err}")
                        continue
            
            return final_markdown.strip() or "No data found."
            
        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            return f"Error fetching page: {str(e)}"
            await context.close()

async def add_comment_action(url: str, base_url: str, comment: str) -> str:
    """Adds a comment to a specific issue."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Adding comment to {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Click Comment button
            comment_btn = page.get_by_text("Comment (on/off)", exact=False)
            if await comment_btn.count() > 0:
                await comment_btn.first.click()
            else:
                # Fallback to simply any link having Comment
                await page.get_by_role("link", name=re.compile("Comment", re.IGNORECASE)).first.click()
                
            await page.wait_for_timeout(2000)
            
            # Fill the Rich Text Editor
            editor = page.get_by_role("textbox", name=re.compile("Editor editing area", re.IGNORECASE))
            if await editor.count() == 0:
                # Fallbacks for popular rich text editors
                editor = page.locator(".ck-editor__editable, [contenteditable='true']").first
                
            if await editor.count() > 0:
                await editor.fill(comment)
            else:
                raise Exception("Could not find the Rich Text Editor area.")
            
            # Click Save
            # Sometimes it's a link named Save, sometimes a button
            save_link = page.get_by_role("link", name=re.compile("Save", re.IGNORECASE))
            if await save_link.count() > 0:
                await save_link.first.click()
            else:
                await page.get_by_role("button", name=re.compile("Save", re.IGNORECASE)).first.click()
                
            await page.wait_for_timeout(2000)
            
            return f"Comment added successfully."
        except Exception as e:
            logger.error(f"Error adding comment to {url}: {e}")
            return f"Error adding comment: {str(e)}"
        finally:
            await context.close()

async def change_status_action(url: str, base_url: str, status: str) -> str:
    """Clicks a status button on a specific issue page."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Changing status of {url} to {status}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            button = page.get_by_role("button", name=re.compile(f"^{status}$", re.IGNORECASE))
            if await button.count() == 0:
                # Try exact text match as fallback
                button = page.get_by_text(status, exact=True)
                
            if await button.count() == 0:
                return f"Error: Status button '{status}' not found on the page."
            
            await button.first.click()
            await page.wait_for_timeout(2000)
            
            return f"Status successfully changed to '{status}'."
        except Exception as e:
            logger.error(f"Error changing status for {url}: {e}")
            return f"Error changing status: {str(e)}"
        finally:
            await context.close()

async def log_time_action(url: str, base_url: str, hours: float, work_notes: str, date: str = None) -> str:
    """Logs time on a specific issue."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Logging {hours}h to {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Switch to time spent tab if exists
            tab = page.get_by_role("tab", name=re.compile("Time Spent", re.IGNORECASE))
            if await tab.count() > 0:
                await tab.first.click()
                await page.wait_for_timeout(1000)
                
            # Click Log time/Edit time spent icon
            log_btn = page.locator("[title='Edit time spent'], [title='Log time']")
            if await log_btn.count() == 0:
                log_btn = page.get_by_text("Log time", exact=False)
                
            if await log_btn.count() > 0:
                await log_btn.first.click()
                await page.wait_for_timeout(1000)
            
            if date:
                date_input = page.get_by_role("textbox", name=re.compile("Log to date", re.IGNORECASE))
                if await date_input.count() > 0:
                    await date_input.fill(date)
            
            notes_input = page.get_by_role("textbox", name=re.compile("Work notes", re.IGNORECASE))
            if await notes_input.count() > 0:
                await notes_input.fill(work_notes)
            
            time_input = page.get_by_role("spinbutton", name=re.compile("Time spent", re.IGNORECASE))
            if await time_input.count() > 0:
                await time_input.fill(str(hours))
                
            save_btn = page.get_by_role("button", name=re.compile("Save", re.IGNORECASE))
            if await save_btn.count() > 0:
                await save_btn.first.click()
            else:
                # Try locating form submit
                await page.locator("form").get_by_role("button").first.click()
                
            await page.wait_for_timeout(2000)
            return f"Logged {hours} hours successfully."
        except Exception as e:
            logger.error(f"Error logging time for {url}: {e}")
            return f"Error logging time: {str(e)}"
        finally:
            await context.close()

async def create_task_action(project_url: str, base_url: str, title: str, description: str = "") -> str:
    """Creates a new task in a project."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Creating task '{title}' in {project_url}")
            await page.goto(project_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Click New * button (New Development, New Task, etc.)
            new_btn = page.get_by_role("link", name=re.compile("New\\s+(Development|Task|Bug|Issue)", re.IGNORECASE))
            if await new_btn.count() == 0:
                # Try fallback: any link containing New
                new_btn = page.get_by_role("link", name=re.compile("New ", re.IGNORECASE))
            if await new_btn.count() == 0:
                # Try fallback: any element containing New Development/Task etc.
                new_btn = page.locator("a, button").filter(has_text=re.compile("New\\s+(Development|Task|Bug|Issue)", re.IGNORECASE))
                
            if await new_btn.count() == 0:
                return "Error: Could not find 'New ...' button on the project page. Ensure the URL is correct (like Backlog/Issue list)."
                
            await new_btn.first.click()
            await page.wait_for_timeout(2000) # Wait for modal/page to load
            
            # Fill Title
            title_input = page.get_by_role("textbox", name=re.compile("^Title$", re.IGNORECASE))
            if await title_input.count() > 0:
                await title_input.fill(title)
            
            # Description
            if description:
                desc_input = page.get_by_role("textbox", name=re.compile("Editor editing area", re.IGNORECASE))
                if await desc_input.count() == 0:
                    desc_input = page.locator(".ck-editor__editable, [contenteditable='true']").first
                    
                if await desc_input.count() > 0:
                    await desc_input.fill(description)

                    
            # Save
            save_btn = page.get_by_role("button", name=re.compile("Save", re.IGNORECASE))
            if await save_btn.count() > 0:
                await save_btn.first.click()
            
            await page.wait_for_timeout(2000)
            return f"Task '{title}' created successfully."
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return f"Error creating task: {str(e)}"
        finally:
            await context.close()

async def delete_comment_action(url: str, base_url: str) -> str:
    """Deletes the latest comment on a specific issue."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Deleting comment on {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            delete_btn = page.locator("[title='Delete comment'], [title='Xóa comment']")
            if await delete_btn.count() == 0:
                delete_btn = page.get_by_title(re.compile("Delete comment", re.IGNORECASE))
                
            if await delete_btn.count() == 0:
                return "Error: Delete comment button not found (you might not have permission or no comment exists)."
                
            # Click the last one (most recent comment usually at the bottom, or just the only one we can delete)
            await delete_btn.last.click()
            await page.wait_for_timeout(1000)
            
            # Click confirm
            confirm_btn = page.get_by_role("button", name=re.compile("Yes, delete it!", re.IGNORECASE))
            if await confirm_btn.count() > 0:
                await confirm_btn.first.click()
            else:
                # Try generic "Yes" or "Delete"
                confirm_btn = page.get_by_role("button", name=re.compile("Yes|Delete|OK", re.IGNORECASE))
                if await confirm_btn.count() > 0:
                    await confirm_btn.first.click()
                    
            await page.wait_for_timeout(2000)
            return "Comment deleted successfully."
        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            return f"Error deleting comment: {str(e)}"
        finally:
            await context.close()

async def edit_description_action(url: str, base_url: str, description: str) -> str:
    """Edits the description of an existing issue."""
    async with async_playwright() as p:
        context = await setup_browser_context(p, base_url)
        page = await context.new_page()
        try:
            logger.info(f"Editing description for {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Click Edit link/button
            edit_btn = page.get_by_role("link", name=re.compile(r"^Edit| Edit$", re.IGNORECASE))
            if await edit_btn.count() == 0:
                edit_btn = page.get_by_text("Edit", exact=True)
            if await edit_btn.count() == 0:
                edit_btn = page.locator("a[title*='Edit']").first
            
            if await edit_btn.count() == 0:
                # If still zero, try fallback clicking any link containing exactly Edit
                edit_btn = page.get_by_text("Edit", exact=False)
                
            if await edit_btn.count() == 0:
                return "Error: Could not find Edit button on the page."
            
            await edit_btn.first.click()
            await page.wait_for_timeout(2000)
            
            # Description
            desc_input = page.get_by_role("textbox", name=re.compile("Editor editing area", re.IGNORECASE))
            if await desc_input.count() == 0:
                desc_input = page.locator(".ck-editor__editable, [contenteditable='true']").first
                
            if await desc_input.count() > 0:
                await desc_input.fill(description)
            else:
                return "Error: Could not find the Rich Text Editor for description."
                
            # Save
            save_btn = page.get_by_role("button", name=re.compile("Save", re.IGNORECASE))
            if await save_btn.count() > 0:
                await save_btn.first.click()
            
            await page.wait_for_timeout(2000)
            return "Description updated successfully."
        except Exception as e:
            logger.error(f"Error editing description: {e}")
            return f"Error editing description: {str(e)}"
        finally:
            await context.close()


