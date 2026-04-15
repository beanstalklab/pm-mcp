import os
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
    
    target_elements = tables + grid_divs
    
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
        finally:
            await context.close()
