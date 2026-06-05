from langchain.tools import tool
from urllib.parse import quote
from DrissionPage import ChromiumPage


class Page(ChromiumPage):
    """
    页面操作单例类
    继承ChromiumPage，全局唯一浏览器实例，避免重复启动Chrome进程
    """
    _instance = None
    _first_init = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, **kwargs):
        # 仅首次实例化初始化浏览器，后续跳过初始化
        if not Page._first_init:
            super().__init__()
            Page._first_init = True


@tool(
    description="""
    实时联网搜索工具，仅在需要最新/实时/今日数据时调用
    适用场景：新闻、价格、政策、实时信息、未知知识
    参数 keyword：搜索关键词，必须简短精准，不要长句子
    返回：多条搜索结果（标题+摘要+来源链接）文本，供LLM参考
    """
)
def online(keyword: str) -> str:
    """bing全网搜索，返回结构化搜索结果摘要"""
    page = Page()
    try:
        q = quote(keyword)
        search_url = f'https://cn.bing.com/search?q={q}'
        page.get(search_url, timeout=8)
        # 等待必应搜索结果渲染
        page.wait.eles_loaded("li.b_algo", timeout=5)

        res_list = []
        # 必应搜索结果条目选择器，取前10条结果
        items = page.eles('xpath://li[@class="b_algo"]')[:10]
        for idx, item in enumerate(items, 1):
            try:
                title = item("xpath:.//h2/a").text.strip()
                link = item("xpath:.//h2/a").link
                summary = item('xpath:.//div[@class="b_caption"]').text.strip()
                res_list.append(
                    f"【{idx}】标题：{title}\n摘要：{summary}\n来源：{link}\n"
                )
            except Exception:
                continue

        if not res_list:
            return "未检索到相关搜索结果"
        return "\n=====搜索结果=====\n" + "".join(res_list)

    except Exception as e:
        return f"联网搜索异常：{str(e)}"

    finally:
        page.close()


@tool(
    description="""
    网页深度精读工具，传入具体网页URL，获取页面完整正文内容
    适用场景：需要详细阅读新闻全文、文章详情、文档内容时调用
    参数 url：需要精读的网页完整链接（https/https开头）
    返回：页面纯净正文文本，供LLM详细分析
    """
)
def online_intensive(url: str) -> str:
    """深度爬取指定URL的网页纯净正文"""
    try:
        page = Page()
        # 访问目标网页
        page.get(url, timeout=10)
        # 等待页面主体加载
        page.wait.doc_loaded(timeout=5)

        # 提取网页标题 + 正文核心内容
        title = page.title.strip()
        # 提取页面所有文本（适配绝大多数网页，自动过滤标签，保留纯净正文）
        content = page.ele("tag:body").text.strip()

        # 控制正文长度，避免过长导致LLM超限
        if len(content) > 8000:
            content = content[:8000] + "……（内容已截断）"

        return f"=====网页精读结果=====\n标题：{title}\n链接：{url}\n正文：\n{content}"

    except Exception as e:
        return f"网页精读异常：{str(e)}"


# 测试运行
if __name__ == "__main__":
    # 测试关键词搜索
    # print(online('今日新闻'))
    # 测试网页深度精读（替换为任意URL即可）
    # print(online_intensive("https://www.baidu.com"))
    print(online_intensive.invoke("https://www.xiangha.com/caipu/t-mianbao/"))