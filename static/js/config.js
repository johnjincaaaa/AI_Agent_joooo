// API 基础地址：自动使用当前访问的域名/端口。
// - 本地运行时页面是 http://127.0.0.1:8000/chat，origin 即 http://127.0.0.1:8000
// - 部署到服务器后是 http://你的域名，origin 即 http://你的域名
// 这样无需手动改地址，本地和服务器都能正常连接后端。
const config = {
    API_BASE_URL: window.location.origin
};
