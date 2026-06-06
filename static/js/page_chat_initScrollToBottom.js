/* ----------------------- 一键滑到底部 ----------------------- */
(function initScrollToBottom() {
    const box = document.getElementById("chatBox");
    const btn = document.getElementById("scrollBottomBtn");
    if (!box || !btn) return;

    // 是否已接近底部（容差 80px）
    function isNearBottom() {
        return box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    }

    // 根据滚动位置显示/隐藏按钮
    function toggleBtn() {
        if (isNearBottom()) {
            btn.classList.remove("show");
        } else {
            btn.classList.add("show");
        }
    }

    // 点击平滑滚动到底部
    btn.addEventListener("click", function () {
        box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
    });

    box.addEventListener("scroll", toggleBtn, { passive: true });

    // 内容变化时（AI 流式输出、加载历史）自动判断是否要显示按钮
    const observer = new MutationObserver(toggleBtn);
    observer.observe(box, { childList: true, subtree: true, characterData: true });

    // 初始化一次
    toggleBtn();
})();