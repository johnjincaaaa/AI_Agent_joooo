from langchain.tools import tool
from ddgs import DDGS
import traceback

@tool(
    description="""
    实时联网搜索工具，仅在需要最新/实时/今日数据时调用
    适用场景：新闻、价格、政策、实时信息、未知知识
    参数 keyword：搜索关键词，必须简短精准，不要长句子
    """
)
def online(keyword: str) -> str:
    try:
        ddgs = DDGS()
        # 纯中文精准搜索
        results = ddgs.text(
            query=keyword,
            region="cn",
            hl="zh-CN",
            max_results=10,
            timeout=60
        )

        if not results:
            return "未搜索到相关实时信息"

        search_result = "联网搜索结果：\n"
        # print(results)
        for i, item in enumerate(results, 1):
            print(f"{i}. {item}")
            search_result += f"{i}. {item['title']}\n摘要：{item['body']}\n\n"

        return search_result.strip() or "未搜索到有效信息"

    except Exception as e:
        print(f"搜索异常：{traceback.format_exc()}{e}")
        return "联网搜索失败，请稍后重试"

# 测试运行
if __name__ == "__main__":
    print(online.invoke("百家乐网站"))