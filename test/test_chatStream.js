async function run() {
  const url = "http://127.0.0.1:8000/ai/chatStream?temperature=0.7";
  const data = {
    history: [{ role: "user", message: "你好" }],
    newMessage: "介绍一下你自己",
    open_online: false
  };

  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const decoder = new TextDecoder('utf-8');
  let buf = '';

  for await (const chunk of res.body) {
    buf += decoder.decode(chunk, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const c = line.trim();
      if (c === '[DONE]') return console.log('\n✅ 完成');
      if (c.startsWith('[HISTORY]')) return console.log('\n📜 历史:', JSON.parse(c));
      process.stdout.write(c);
    }
  }
}

run();