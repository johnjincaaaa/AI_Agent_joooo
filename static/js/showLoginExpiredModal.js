// 🔥 终极豪华版：登录过期弹窗（毛玻璃 + 动画 + 图标 + 按钮）
function showLoginExpiredModal(meg) {
    // 遮罩层
    const overlay = document.createElement('div');
    overlay.style.cssText = `
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0, 0, 0, 0.4); z-index: 9999;
    backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center;
    animation: fadeIn 0.3s ease forwards;
  `;

    // 弹窗主体（毛玻璃 + 滑入动画）
    const modal = document.createElement('div');
    modal.style.cssText = `
    width: 320px; background: rgba(255,255,255,0.25); backdrop-filter: blur(20px);
    border-radius: 20px; padding: 30px; text-align: center; color: #fff;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2);
    animation: slideIn 0.5s cubic-bezier(0.25, 1, 0.5, 1) forwards;
  `;

    // 动画样式
    const style = document.createElement('style');
    style.textContent = `
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    @keyframes slideIn { from { transform: translateY(40px) scale(0.95); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    @keyframes breath { 0% { box-shadow: 0 8px 32px rgba(255,80,80,0.4); } 50% { box-shadow: 0 8px 32px rgba(255,80,80,0.8); } 100% { box-shadow: 0 8px 32px rgba(255,80,80,0.4); } }
  `;
    document.head.appendChild(style);
    modal.style.animation = 'breath 2s infinite ease-in-out, slideIn 0.5s ease';

    // 图标
    modal.innerHTML = `
    <div style="font-size: 50px; margin-bottom: 16px;">🔒</div>
    <h2 style="margin: 0 0 8px 0; font-size: 18px;">${meg}</h2>
    <p style="margin:0 0 24px 0; font-size:14px; opacity:0.9;">请重新登录后继续使用</p>
    <button id="loginModalBtn" style="padding:12px 24px; border-radius:12px; border:none; background:#ff4b4b; color:#fff; font-weight:bold; cursor:pointer; width:100%;">立即登录</button>
  `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // 按钮点击
    document.getElementById('loginModalBtn').onclick = () => {
        document.body.removeChild(overlay);
        document.getElementById('openLoginBtn').click(); // 触发你的登录按钮
    };
}