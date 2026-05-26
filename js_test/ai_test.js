const API_KEY = "123";
const API_URL = "http://localhost:11434";
async function chat() {
     const queryString = new URLSearchParams(params).toString();
  const res = await fetch("http://localhost:11434/api/chat",{
    method:"POST",
    headers:{"Content-Type":"application/json"},

  });
  const data = await res.json();
  console.log(data.message);
}
chat();
