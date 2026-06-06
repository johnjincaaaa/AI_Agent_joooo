import requests
import json

url = "http://127.0.0.1:8000/ai/chatStream?temperature=0.7"
data = {
    "history": [{"role": "user", "message": "你好"}],
    "newMessage": "讲个故事",
    "open_online": False
}

# 接收流式响应
response = requests.post(url, json=data, stream=True)
full_text = ""
final_history = None

for line in response.iter_lines(decode_unicode=True):
    if not line:
        continue
    if line.startswith("data: "):
        content = line.replace("data: ", "").strip()

        # 1. 结束标记
        if content == "[DONE]":
            print("\n=== 流式结束 ===")
            break

        # 2. 接收完整历史（核心！）
        elif content.startswith("[HISTORY]"):
            history_json = content.replace("[HISTORY] ", "").strip()
            final_history = json.loads(history_json)
            print("\n=== 完整对话历史 ===")
            print(final_history)

        # 3. 实时渲染流式文字
        else:
            full_text += content
            print(content, end="")

# 最终可以使用完整历史
print("\n\nAI完整回答：", full_text)
print("完整对话记录：", final_history)