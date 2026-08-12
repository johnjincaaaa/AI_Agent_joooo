"""
Browser MCP：浏览器自动化工具（基于 Playwright）
包含：打开页面、截图、点击、填写表单、提取内容等
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def register_browser_tools(manager):
    """注册浏览器自动化相关工具。"""

    manager.register_tool(
        name="mcp_browser_goto",
        func=browser_goto,
        description="打开指定 URL 的网页。",
        parameters={"url": "要打开的网页 URL"},
    )

    manager.register_tool(
        name="mcp_browser_screenshot",
        func=browser_screenshot,
        description="对当前页面进行截图，保存为图片文件。",
        parameters={"path": "截图保存路径（.png）", "full_page": "是否整页截图，默认 true"},
    )

    manager.register_tool(
        name="mcp_browser_click",
        func=browser_click,
        description="点击页面上指定的元素。",
        parameters={"selector": "元素选择器（CSS selector）"},
    )

    manager.register_tool(
        name="mcp_browser_fill",
        func=browser_fill,
        description="在输入框中填写内容。",
        parameters={"selector": "输入框选择器", "value": "要填写的内容"},
    )

    manager.register_tool(
        name="mcp_browser_extract",
        func=browser_extract,
        description="提取页面内容或指定元素的文本。",
        parameters={"selector": "元素选择器（可选，留空则提取整页文本）"},
    )

    manager.register_tool(
        name="mcp_browser_close",
        func=browser_close,
        description="关闭浏览器。",
        parameters={},
    )


# 全局浏览器实例
_browser = None
_page = None


def _get_browser():
    """获取或启动浏览器实例。"""
    global _browser, _page
    if _browser is None:
        try:
            from playwright.sync_api import sync_playwright
            _p = sync_playwright().start()
            _browser = _p.chromium.launch(headless=True)
            _page = _browser.new_page()
            logger.info("[Browser MCP] 浏览器已启动")
        except ImportError:
            raise RuntimeError("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
        except Exception as e:
            raise RuntimeError(f"浏览器启动失败: {e}")
    return _page


def browser_goto(url: str) -> str:
    """打开指定 URL。"""
    try:
        if not url:
            return "错误：请提供 URL"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        page = _get_browser()
        page.goto(url, timeout=30000)
        title = page.title()
        return f"成功：已打开 {url}\n页面标题: {title}"
    except Exception as e:
        return f"打开网页失败: {str(e)}"


def browser_screenshot(path: str = "", full_page: bool = True) -> str:
    """截图。"""
    try:
        page = _get_browser()
        if not path:
            from datetime import datetime
            path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        page.screenshot(path=path, full_page=full_page)
        return f"成功：截图已保存到 {path}"
    except Exception as e:
        return f"截图失败: {str(e)}"


def browser_click(selector: str) -> str:
    """点击元素。"""
    try:
        if not selector:
            return "错误：请提供元素选择器"
        page = _get_browser()
        page.click(selector, timeout=10000)
        return f"成功：已点击 {selector}"
    except Exception as e:
        return f"点击元素失败: {str(e)}"


def browser_fill(selector: str, value: str) -> str:
    """填写输入框。"""
    try:
        if not selector:
            return "错误：请提供输入框选择器"
        page = _get_browser()
        page.fill(selector, value, timeout=10000)
        return f"成功：已在 {selector} 中填写内容"
    except Exception as e:
        return f"填写输入框失败: {str(e)}"


def browser_extract(selector: str = "") -> str:
    """提取页面内容。"""
    try:
        page = _get_browser()
        if selector:
            element = page.query_selector(selector)
            if element:
                text = element.inner_text()
            else:
                return f"错误：未找到选择器 {selector} 对应的元素"
        else:
            text = page.inner_text("body")

        if len(text) > 10000:
            text = text[:10000] + "\n...(内容过长，已截断)"
        return f"===== 提取的内容 =====\n{text}"
    except Exception as e:
        return f"提取内容失败: {str(e)}"


def browser_close() -> str:
    """关闭浏览器。"""
    global _browser, _page
    try:
        if _browser:
            _browser.close()
            _browser = None
            _page = None
            return "成功：浏览器已关闭"
        return "浏览器未运行"
    except Exception as e:
        return f"关闭浏览器失败: {str(e)}"
