/**
 * dsh-pet 轻量 WebM 播放器 —— 独立浏览器版桌宠前端。
 *
 * 从 dsh-pet（DSH 插件）拆出的简化版：
 *   - 只依赖透明 WebM 动画资产 + 原生 JS，不依赖 React / DSH 模块系统
 *   - 支持：待机呼吸、随机动作循环、点击回应、拖拽甩抛、屏幕漫游、右键菜单点播
 *   - 碎碎念（定时随机说话 + 表情包配图）、AI 状态联动、反向对话
 *
 * 配置注入：window.__DSH_PET_BOOT__ = { base, assetBase }
 */
;(function () {
  'use strict'

  if (window.__DSH_PET_LOADED__) return
  window.__DSH_PET_LOADED__ = true

  const BOOT = window.__DSH_PET_BOOT__ || {}
  const BASE = BOOT.base || '/plugins/dsh-pet'
  const ASSET_BASE = BOOT.assetBase || (BASE + '/assets')
  const WEBM_DIR = ASSET_BASE + '/webm'
  const MEMES_DIR = ASSET_BASE + '/memes'
  const SOUND_DIR = ASSET_BASE + '/sound'

  // 用户自定义资源（后端合并配置返回后填入）
  let USER_DIR = null          // 如 /plugins/dsh-pet/user-assets/42
  let USER_ASSETS = { webm: [], memes: [], sound: [] }
  let PET_DIR = null           // 当前安装的宠物包资源目录 /plugins/pets/<id>
  let PET_WEBMS = []           // 宠物包内的动画名清单（优先从 PET_DIR 加载）
  let PET_MEMES = []           // 宠物包内自带的表情包名清单（切宠物后表情包也跟着换）

  // ── 可调配置（改这里，不用往下翻）──────────────────────
  const CONFIG = {
    // 碎碎念：间隔（毫秒），min~max 随机
    whisperMinMs: 9000,
    whisperMaxMs: 18000,
    // 碎碎念配表情包概率（0~1）
    whisperMemeChance: 0.4,
    // 碎碎念气泡显示时长（毫秒）
    whisperBubbleMs: 5000,
    // 随机动作间隔（毫秒），min~max
    randomMinMs: 8000,
    randomMaxMs: 20000,
  }

  // ── 动画池（内置默认；启动时用后端合并配置覆盖/追加）──────────────
  let POOLS = {
    idle: ['待机呼吸休闲'],
    // 转向（播完翻转朝向）
    turn: ['东张西望'],
    // 拖拽（被抓起悬空）
    drag: ['被鼠标拖拽悬空反馈'],
    // 移动（自己走位）
    moves: ['螃蟹走路', '原地漂浮踏步', '原地左转奔跑'],
    // 点击回应
    clicks: [
      '点击回应-开心跃动',
      '点击回应-害羞惊讶',
      '点击回应-傲娇生气',
      '点击回应-挠痒咯咯笑',
      '点击回应-元气挥手',
    ],
    // 随机小动作 / 玩耍 / 吃什么（合并随机池）
    random: [
      '悠闲哼歌', '超大伸懒腰', '原地敲击桌面互动', '原地重力下蹲压缩', '哈欠连天',
      '原地小憩沉眠', '女仆屈膝礼仪', '被吓一跳', '小幅度原地360度旋转展示',
      '偷吃零食被抓住', '用鲸鱼尾巴拍打地面', '打瞌睡被惊醒', '照镜子', '整体换装试色',
      '轻快记录', '写代码', '摇扇纳凉', '晨间刷牙', '原地专心玩魔方', '原地蹲下玩玩具汽车',
      '鲸鱼吐泡泡特效', '原地跳跃抓碎头顶物品', '玩游戏气急败坏', '玩水枪',
      '小提琴演奏', '蓝鲸现世', '优雅女仆舞', '轻快摇摆舞', '可爱宅舞', '吹气球',
      '动物环绕', '放风筝', '拆礼物', '变鸽子', '扑克魔术', '抽陀螺', '吹笛子',
      '蝴蝶蜜蜂环绕头顶开花', '撸猫', '凭空生花', '骑木马', '三球抛接', '踢毽子',
      '下五子棋', '荡秋千', '吃白饭', '大口吃零食', '吃Token', '吃早餐', '吃午餐',
      '吃晚餐', '吃冰淇淋融化', '吃大闸蟹', '吃糖葫芦', '吃长寿面', '吃西瓜', '涮火锅',
    ],
    // 时节（节日/季节）
    seasonal: [
      '被落叶淹没', '中秋赏月吃月饼', '堆雪人', '放烟花', '吃粽子', '吃年糕', '吃青团',
      '吃腊八粥', '吃重阳糕', '收红包', '写福字', '穿针乞巧', '舞狮头', '讨糖南瓜灯',
      '插茱萸赏菊', '放河灯', '萌化小幽灵', '装点圣诞树', '放孔明灯', '吃汤圆', '吃饺子',
    ],
    // 文字梗
    textMeme: ['是啊，吃什么', '深度思考碎碎念'],
    // 碎碎念动画
    whisper: ['碎碎念-擦桌碎碎念', '碎碎念-发呆碎碎念', '碎碎念-对屏碎碎念'],
    // 工作状态（事件联动）
    workStatus: [
      '工作状态-思考冒泡',      // 0 thinking
      '工作状态-忙碌点按',      // 1 working
      '工作状态-清点归档',      // 2 result
      '工作状态-原地踱步张望',  // 3 waiting
      '工作状态-雀跃庆祝',      // 4 success
      '工作状态-垂头叹气冒汗',  // 5 error
    ],
  }

  // ── 表情包（内置默认；启动时用后端合并配置覆盖/追加）──────────────
  let MEMES = {
    '吃白饭的大肥鱼': '躺平扒白饭，摆烂挨骂也无所谓',
    '大的要来啦': '举喇叭大喊预警',
    '大的药来了': '抱着超大胶囊，谐音梗',
    '要不直接骂他': '气愤指着前方要骂人',
    '死掉了': '翻肚皮躺平灵魂出窍',
    '深度睡眠': '趴着呼呼大睡冒 Zzz',
    '大烧货': '死鱼眼吐槽想得慢',
    '先养着吧': '搂着一群小鲸鱼',
    '吃饱饱摸肚子': '侧躺拍肚子说吃饱饱',
    '誓死践行开源精神': '庄重敬礼表态',
    '电死你': '举电击器放电',
    '可爱': '标准正面卖萌立绘',
    'token给妈妈保管': '伸手过来要 token',
  }

  // ── 音效（名称 → 文件名；用户可上传 sound 覆盖/追加）──────────────
  let SOUNDS = {
    'click-duck': 'click-duck.wav',
  }

  // ── 后端合并配置缓存 ──────────────────────────────────
  let REMOTE_CFG = null

  const LS_KEY = 'dsh-pet:layout'

  // ── 状态 ──────────────────────────────────────────────
  const state = {
    current: null,        // 当前播放的动画名
    loop: true,
    randomTimer: null,
    whisperTimer: null,
    facing: 1,            // 1 = 右, -1 = 左（镜像）
    sleeping: false,
    lastActivity: Date.now(),
  }

  // ── 资源内存缓存（避免重复请求动画/表情/音效）────────────
  // 首次 fetch 转 blob URL 缓存；后续同一资源直接读内存，不再走网络。
  // 网络波动时已缓存的资源照常播放，宠物不会因资源加载失败而消失。
  const resourceCache = new Map()   // url -> objectURL(blob)
  const pendingFetches = new Map()  // url -> Promise<objectURL>

  function getCachedResource(url) {
    return resourceCache.get(url) || null
  }

  async function fetchResource(url) {
    const hit = resourceCache.get(url)
    if (hit) return hit
    let p = pendingFetches.get(url)
    if (!p) {
      p = fetch(url, { cache: 'force-cache' })
        .then(res => {
          if (!res.ok) throw new Error('HTTP ' + res.status)
          return res.blob()
        })
        .then(blob => {
          const objectUrl = URL.createObjectURL(blob)
          resourceCache.set(url, objectUrl)
          pendingFetches.delete(url)
          return objectUrl
        })
        .catch(err => {
          pendingFetches.delete(url)
          throw err
        })
      pendingFetches.set(url, p)
    }
    return p
  }

  // ── 音效 ──────────────────────────────────────────────
  let audioCtx = null

  // 资源路径解析：当前宠物包优先 → 用户上传 → 内置
  function resolveAsset(kind, name, ext) {
    const dirMap = { webm: 'webm', memes: 'memes', sound: 'sound' }
    // 1. 当前宠物包（插件市场安装的 DSH pet）
    if (kind === 'webm' && PET_DIR && PET_WEBMS.indexOf(name) >= 0) {
      return PET_DIR + '/webm/' + encodeURIComponent(name) + ext
    }
    // 1b. 当前宠物包自带的表情包（切宠物后表情包也跟着换，不再回退大肥鱼）
    if (kind === 'memes' && PET_DIR && PET_MEMES.indexOf(name) >= 0) {
      return PET_DIR + '/memes/' + encodeURIComponent(name) + ext
    }
    // 2. 用户上传
    if (USER_DIR) {
      const list = USER_ASSETS[kind] || []
      if (list.indexOf(name) >= 0) {
        return USER_DIR + '/' + dirMap[kind] + '/' + encodeURIComponent(name) + ext
      }
    }
    // 3. 内置
    const builtinDir = { webm: WEBM_DIR, memes: MEMES_DIR, sound: SOUND_DIR }
    return builtinDir[kind] + '/' + encodeURIComponent(name) + ext
  }

  function playClickSound() {
    try {
      // 点击音效开关（默认开启，与 config.jsonc 一致）
      if (!REMOTE_CFG || !REMOTE_CFG.settings || !REMOTE_CFG.settings.clickSoundEnabled) return
      const file = SOUNDS['click-duck'] || 'click-duck.wav'
      const dot = file.lastIndexOf('.')
      const stem = dot > 0 ? file.slice(0, dot) : file
      const ext = dot > 0 ? file.slice(dot) : '.wav'
      const src = resolveAsset('sound', stem, ext)
      const cached = getCachedResource(src)
      if (cached) {
        const audio = new Audio(cached)
        audio.volume = 0.5
        audio.play().catch(() => {})
      } else {
        fetchResource(src).then(blobUrl => {
          const audio = new Audio(blobUrl)
          audio.volume = 0.5
          audio.play().catch(() => {})
        }).catch(() => {})
      }
    } catch (e) {}
  }

  // ── DOM 构建 ──────────────────────────────────────────
  function buildUI() {
    const root = document.createElement('div')
    root.id = 'dshp-root'
    root.style.cssText = [
      'position:fixed', 'z-index:2147483000', 'right:24px', 'top:100px',
      'width:280px', 'height:218px', 'cursor:grab', 'user-select:none',
      'pointer-events:auto', 'transition:none', 'will-change:transform',
    ].join(';')

    const video = document.createElement('video')
    video.id = 'dshp-video'
    video.autoplay = true
    video.muted = true
    video.playsInline = true
    video.loop = true
    video.style.cssText = 'width:100%;height:100%;object-fit:contain;pointer-events:none;'
    root.appendChild(video)

    // 气泡（支持文字 + 表情包配图）
    const bubble = document.createElement('div')
    bubble.id = 'dshp-bubble'
    bubble.style.cssText = [
      'position:absolute', 'top:-8px', 'left:50%', 'transform:translate(-50%,-100%)',
      'background:rgba(255,255,255,0.95)', 'color:#333', 'padding:6px 12px',
      'border-radius:12px', 'font-size:13px', 'max-width:220px', 'text-align:center',
      'display:none', 'box-shadow:0 2px 8px rgba(0,0,0,0.15)',
      'white-space:normal', 'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
    ].join(';')
    root.appendChild(bubble)

    // 隐藏后的把手（悬浮球，右下角，点击恢复桌宠）
    const handle = document.createElement('div')
    handle.id = 'dshp-handle'
    handle.style.cssText = [
      'position:fixed', 'z-index:2147483001', 'right:16px', 'bottom:16px',
      'width:48px', 'height:48px', 'border-radius:50%',
      'background:#7c5cff', 'color:#fff', 'font-size:24px', 'line-height:48px',
      'text-align:center', 'cursor:pointer', 'user-select:none',
      'display:none', 'box-shadow:0 2px 12px rgba(0,0,0,0.3)',
      'transition:transform 0.15s',
    ].join(';')
    handle.innerHTML = '<svg width="24" height="24" viewBox="0 0 27 22" fill="currentColor" style="display:block;margin:12px auto"><path d="M26.5174 3.39471C26.235 3.2567 26.1137 3.52006 25.9487 3.65346C25.8923 3.69659 25.8446 3.75294 25.7969 3.80469C25.3846 4.24516 24.9027 4.53439 24.2737 4.49989C23.3536 4.44814 22.5682 4.73737 21.8735 5.44119C21.7258 4.57349 21.2353 4.0554 20.4889 3.72304C20.0985 3.55054 19.7034 3.37746 19.4297 3.00197C19.2388 2.73459 19.1865 2.43673 19.091 2.14289C19.0301 1.96579 18.9697 1.78466 18.7656 1.75418C18.5442 1.71968 18.4574 1.90541 18.3705 2.06067C18.0232 2.69549 17.8887 3.39471 17.9019 4.10313C17.9324 5.6965 18.6051 6.96556 19.9421 7.86834C20.0939 7.97184 20.133 8.07535 20.0852 8.22658C19.9938 8.53766 19.8857 8.83955 19.7903 9.15063C19.7293 9.34901 19.6384 9.39271 19.4257 9.30588C18.692 8.9994 18.0583 8.54571 17.4982 7.99772C16.5477 7.07827 15.6881 6.06336 14.6162 5.26869C14.3644 5.08296 14.1125 4.91045 13.8521 4.746C12.7584 3.68394 13.9952 2.81164 14.2816 2.70814C14.5812 2.60003 14.3857 2.22857 13.4179 2.23317C12.4502 2.2372 11.5646 2.56151 10.4359 2.99335C10.2708 3.05832 10.0972 3.10547 9.91951 3.14457C8.8954 2.95022 7.83162 2.90709 6.72069 3.03245C4.62877 3.26533 2.95777 4.25436 1.72954 5.94261C0.254043 7.97184 -0.0932678 10.2777 0.33167 12.6824C0.778458 15.2171 2.07225 17.3153 4.06008 18.9558C6.12152 20.6567 8.49577 21.4905 11.2047 21.3306C12.8498 21.2358 14.6812 21.0155 16.7473 19.2669C17.2682 19.5262 17.8151 19.6297 18.7219 19.7074C19.4205 19.7723 20.0933 19.6729 20.6143 19.5648C21.4302 19.3923 21.3739 18.6367 21.0789 18.4981C18.6874 17.3843 19.2124 17.8374 18.7351 17.4706C19.9501 16.033 21.8063 13.4776 22.379 9.99821C22.4353 9.61409 22.5072 9.073 22.4986 8.76192C22.494 8.57216 22.5377 8.49856 22.7545 8.47671C23.3536 8.40771 23.935 8.24383 24.4692 7.94999C26.0188 7.10357 26.6439 5.71318 26.7911 4.04678C26.8129 3.79204 26.7865 3.52869 26.5174 3.39471ZM13.0143 18.3946C10.6964 16.5724 9.5722 15.9726 9.10816 15.9985C8.67402 16.0244 8.75222 16.5212 8.84768 16.8449C8.94773 17.1646 9.07768 17.3849 9.25996 17.6655C9.38589 17.8512 9.47272 18.1272 9.13404 18.3348C8.38766 18.7965 7.08985 18.1796 7.0289 18.1491C5.51833 17.2595 4.25559 16.0853 3.36546 14.4793C2.50581 12.9337 2.0067 11.2753 1.92447 9.50542C1.90262 9.07818 2.02855 8.92695 2.45406 8.84932C3.01413 8.74582 3.59144 8.72397 4.15093 8.80619C6.51656 9.15178 8.53027 10.2092 10.2185 11.8848C11.1822 12.8388 11.9114 13.979 12.6623 15.0929C13.461 16.2757 14.3201 17.4027 15.4144 18.3268C15.8008 18.6505 16.109 18.8966 16.404 19.0783C15.5144 19.1778 14.0297 19.1991 13.0143 18.3958V18.3946ZM14.1252 11.2489C14.1252 11.0591 14.277 10.9079 14.4679 10.9079C14.511 10.9079 14.5501 10.9165 14.5852 10.9292C14.6329 10.9464 14.6766 10.9723 14.7111 11.0114C14.7721 11.0718 14.8066 11.158 14.8066 11.2489C14.8066 11.4386 14.6548 11.5899 14.4639 11.5899C14.273 11.5899 14.1252 11.4386 14.1252 11.2489ZM17.5759 13.0188C17.3545 13.1096 17.1331 13.1873 16.9203 13.1959C16.5903 13.2131 16.2303 13.0791 16.0348 12.9153C15.7312 12.6605 15.5139 12.5179 15.423 12.0734C15.3839 11.8837 15.4057 11.5899 15.4402 11.4214C15.5185 11.0585 15.4316 10.8257 15.1757 10.614C14.9676 10.4415 14.7025 10.3938 14.4115 10.3938C14.3029 10.3938 14.2034 10.3461 14.1292 10.3076C14.0079 10.2472 13.9078 10.096 14.0033 9.91023C14.0338 9.84985 14.1815 9.70322 14.216 9.67734C14.6111 9.45251 15.0665 9.52612 15.488 9.6946C15.8784 9.85445 16.174 10.1477 16.5989 10.5623C17.033 11.0631 17.1112 11.2011 17.3585 11.5772C17.554 11.871 17.7317 12.1729 17.8536 12.5185C17.9272 12.7341 17.8317 12.9107 17.5759 13.0188Z"/></svg>';
    handle.title = '召唤桌宠'
    handle.onmouseenter = () => { handle.style.transform = 'scale(1.1)' }
    handle.onmouseleave = () => { handle.style.transform = 'scale(1)' }
    handle.onclick = () => showPet()
    document.body.appendChild(handle)

    document.body.appendChild(root)
    return { root, video, bubble, handle }
  }

  const ui = buildUI()

  // ── 显示 / 隐藏 ──────────────────────────────────────
  function hidePet() {
    ui.root.style.display = 'none'
    ui.handle.style.display = 'block'
  }

  function showPet() {
    ui.root.style.display = 'block'
    ui.handle.style.display = 'none'
    // 恢复时重置动画
    playIdle()
    scheduleNextRandom()
  }

  function showBubble(text, ms, memeName) {
    if (!text) { ui.bubble.style.display = 'none'; return }
    // 文字先立即显示，表情包异步走缓存：不阻塞气泡、不重复请求
    ui.bubble.innerHTML = `<span>${escapeHtml(text)}</span>`
    ui.bubble.style.display = 'block'
    if (memeName) {
      const imgSrc = resolveAsset('memes', memeName, '.png')
      const img = document.createElement('img')
      img.style.cssText = 'width:100%;border-radius:8px;display:block;margin-bottom:4px;'
      const cached = getCachedResource(imgSrc)
      if (cached) {
        img.src = cached
        ui.bubble.insertBefore(img, ui.bubble.firstChild)
      } else {
        fetchResource(imgSrc).then(blobUrl => {
          // 气泡期间若已切走，不再插入
          if (ui.bubble.style.display === 'none') return
          img.src = blobUrl
          ui.bubble.insertBefore(img, ui.bubble.firstChild)
        }).catch(() => {})
      }
    }
    clearTimeout(showBubble._t)
    if (ms) {
      showBubble._t = setTimeout(() => { ui.bubble.style.display = 'none' }, ms)
    }
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c])
  }

  // ── 动画播放 ──────────────────────────────────────────
  function playAnim(name, loop, keepFacing) {
    if (!name) return
    const src = resolveAsset('webm', name, '.webm')
    state.current = name
    ui.video.style.display = ''
    ui.video.loop = !!loop
    // 镜像：转向动画不镜像，其余按 facing
    if (!keepFacing && state.facing === -1) {
      ui.video.style.transform = 'scaleX(-1)'
    } else {
      ui.video.style.transform = ''
    }
    state.lastActivity = Date.now()
    state.sleeping = false

    const cached = getCachedResource(src)
    if (cached) {
      // 命中缓存：直接播，不再发网络请求
      ui.video.src = cached
      ui.video.play().catch(() => {})
      return
    }
    // 未命中：拉取成 blob 缓存后再播；快速切换时只有当前动画才上屏
    fetchResource(src).then(blobUrl => {
      if (state.current !== name) return
      ui.video.src = blobUrl
      ui.video.play().catch(() => {})
    }).catch(() => {
      // 网络失败：保留当前帧不黑屏；下一次切动画会自动重试
    })
  }

  function pickRandom(arr) {
    return arr[Math.floor(Math.random() * arr.length)]
  }

  function playIdle() {
    const name = pickRandom(POOLS.idle)
    if (name) playAnim(name, true)
  }

  // 语义化播放：按「角色」从当前宠物的 POOLS 取动画，而不是写死大肥鱼动画名。
  // workStatus 池按约定顺序映射：0思考 1忙碌 2整理 3等待 4庆祝 5出错。
  // 池为空（如精简包）时优雅降级：workStatus 回退 idle，
  // 取不到就保持当前动画不动——绝不加载不存在的 webm 导致 404 闪烁/消失。
  const WORK_STATUS_INDEX = { thinking: 0, working: 1, result: 2, waiting: 3, success: 4, error: 5 }

  function workStatusAnim(key) {
    const pool = POOLS.workStatus || []
    const idx = WORK_STATUS_INDEX[key]
    if (idx != null && pool[idx]) return pool[idx]
    // 宠物没有 workStatus 池 → 用随机/待机兜底
    return pickRandom(pool) || pickRandom(POOLS.idle)
  }

  // 按角色播放动画；取不到名字则不动（保持当前帧），返回是否真的切了动画
  function playByRole(role, loop) {
    let name = null
    if (role === 'idle') name = pickRandom(POOLS.idle)
    else if (role === 'whisper') name = pickRandom(POOLS.whisper) || pickRandom(POOLS.random) || pickRandom(POOLS.idle)
    else name = workStatusAnim(role)   // thinking/working/result/waiting/success/error
    if (!name) return false
    playAnim(name, loop)
    return true
  }

  function playRandomAction() {
    // 随机动作：优先 random 池，空则用 seasonal，再空则待机兜底
    let pool = (Math.random() < 0.75 && POOLS.random.length) ? POOLS.random : POOLS.seasonal
    if (!pool || !pool.length) pool = POOLS.random
    const name = pickRandom(pool)
    if (name) {
      playAnim(name, false)
      ui.video.onended = () => { playIdle(); scheduleNextRandom() }
    } else {
      // 该宠物没有随机动作 → 跳过本次，稍后再试，保持待机
      scheduleNextRandom()
    }
  }

  function scheduleNextRandom() {
    clearTimeout(state.randomTimer)
    const delay = CONFIG.randomMinMs + Math.random() * (CONFIG.randomMaxMs - CONFIG.randomMinMs)
    state.randomTimer = setTimeout(() => {
      if (document.hidden) { scheduleNextRandom(); return }
      playRandomAction()
    }, delay)
  }

  // ── 点击回应 ──────────────────────────────────────────
  function onPointerClick(e) {
    if (e.button !== 0) return
    if (movedDuringDrag) return  // 拖拽后不触发点击
    playClickSound()
    playAnim(pickRandom(POOLS.clicks), false)
    ui.video.onended = () => { playIdle(); scheduleNextRandom() }
  }

  // ── 拖拽（含甩抛物理）─────────────────────────────────
  let dragging = false
  let movedDuringDrag = false
  let dragStart = { x: 0, y: 0, left: 0, top: 0 }
  let velocity = { vx: 0, vy: 0 }
  let lastMoveTime = 0
  let lastMoveX = 0
  let lastMoveY = 0
  let momentumAnim = null  // 甩抛动画帧

  function onPointerDown(e) {
    dragging = true
    movedDuringDrag = false
    dragStart = {
      x: e.clientX, y: e.clientY,
      left: ui.root.offsetLeft, top: ui.root.offsetTop,
    }
    velocity = { vx: 0, vy: 0 }
    lastMoveX = e.clientX
    lastMoveY = e.clientY
    lastMoveTime = Date.now()
    ui.root.style.cursor = 'grabbing'
    // 拖拽动画
    playAnim(pickRandom(POOLS.drag), true, true)
    e.preventDefault()
    stopMomentum()
  }

  function onPointerMove(e) {
    if (!dragging) return
    const dx = e.clientX - dragStart.x
    const dy = e.clientY - dragStart.y
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) movedDuringDrag = true

    const now = Date.now()
    const dt = Math.max(1, now - lastMoveTime)
    const ivx = (e.clientX - lastMoveX) / dt * 13  // 归一化速度（甩抛初速度）
    const ivy = (e.clientY - lastMoveY) / dt * 13
    velocity = { vx: ivx, vy: ivy }
    lastMoveX = e.clientX
    lastMoveY = e.clientY
    lastMoveTime = now

    // 边界钳制：桌宠始终留在视口内，避免拖出屏幕后拉不回来
    const w = ui.root.offsetWidth
    const h = ui.root.offsetHeight
    const maxX = window.innerWidth - w
    const maxY = window.innerHeight - h
    const newLeft = Math.max(0, Math.min(maxX, dragStart.left + dx))
    const newTop = Math.max(0, Math.min(maxY, dragStart.top + dy))
    ui.root.style.left = newLeft + 'px'
    ui.root.style.top = newTop + 'px'
    ui.root.style.right = 'auto'
  }

  function onPointerUp() {
    if (!dragging) return
    dragging = false
    ui.root.style.cursor = 'grab'
    saveLayout()
    // 甩抛：速度够快就带惯性飞出去 + 反弹
    const speed = Math.sqrt(velocity.vx * velocity.vx + velocity.vy * velocity.vy)
    if (speed > 2 && movedDuringDrag) {
      startMomentum(velocity.vx, velocity.vy)
    } else {
      playIdle()
    }
  }

  function stopMomentum() {
    if (momentumAnim) { cancelAnimationFrame(momentumAnim); momentumAnim = null }
  }

  function startMomentum(vx, vy) {
    stopMomentum()
    // 最大速度钳制：极端甩动也不会飞太快
    const MAX_V = 32
    vx = Math.max(-MAX_V, Math.min(MAX_V, vx))
    vy = Math.max(-MAX_V, Math.min(MAX_V, vy))
    let x = ui.root.offsetLeft
    let y = ui.root.offsetTop
    const damping = 0.90  // 阻尼（惯性衰减，顺滑）
    const bounce = 0.55   // 反弹系数

    function step() {
      vx *= damping
      vy *= damping
      vy += 0.30  // 重力（更轻，下坠缓）
      x += vx
      y += vy

      // 边界反弹
      const w = ui.root.offsetWidth
      const h = ui.root.offsetHeight
      const maxX = window.innerWidth - w
      const maxY = window.innerHeight - h
      if (x < 0) { x = 0; vx = -vx * bounce }
      if (x > maxX) { x = maxX; vx = -vx * bounce }
      if (y < 0) { y = 0; vy = -vy * bounce }
      if (y > maxY) { y = maxY; vy = -vy * bounce; vx *= 0.9 }

      ui.root.style.left = x + 'px'
      ui.root.style.top = y + 'px'
      ui.root.style.right = 'auto'

      const speed = Math.sqrt(vx * vx + vy * vy)
      if (speed > 0.3) {
        momentumAnim = requestAnimationFrame(step)
      } else {
        momentumAnim = null
        saveLayout()
        playIdle()
      }
    }
    momentumAnim = requestAnimationFrame(step)
  }

  function saveLayout() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({
        left: ui.root.offsetLeft, top: ui.root.offsetTop,
      }))
    } catch (e) {}
  }

  // ── 右键菜单（一级「更多」→ 二级全部动作 + 表情包）──
  const MENU_CSS = [
    'position:fixed', 'z-index:2147483001', 'background:#fff', 'border-radius:8px',
    'box-shadow:0 4px 16px rgba(0,0,0,0.2)', 'padding:4px 0', 'display:none',
    'min-width:150px', 'font-size:13px', 'color:#333', 'border:1px solid #ddd',
    'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
    'max-height:70vh', 'overflow-y:auto',
  ].join(';')

  const menu = document.createElement('div')
  menu.id = 'dshp-menu'
  menu.style.cssText = MENU_CSS
  document.body.appendChild(menu)

  const submenu = document.createElement('div')
  submenu.id = 'dshp-submenu'
  submenu.style.cssText = MENU_CSS
  document.body.appendChild(submenu)

  let submenuHideTimer = null
  function hideAllMenus() {
    menu.style.display = 'none'
    submenu.style.display = 'none'
    clearTimeout(submenuHideTimer)
  }
  function scheduleSubmenuHide() {
    clearTimeout(submenuHideTimer)
    submenuHideTimer = setTimeout(() => { submenu.style.display = 'none' }, 250)
  }

  // 二级菜单：列出所有动画动作 + 表情包
  function buildSubmenuItems() {
    const frag = document.createDocumentFragment()
    const addSep = () => {
      const s = document.createElement('div')
      s.style.cssText = 'border-top:1px solid #eee;margin:4px 0'
      frag.appendChild(s)
    }
    const addGroup = (t) => {
      const g = document.createElement('div')
      g.textContent = t
      g.style.cssText = 'padding:4px 16px 2px;font-size:11px;color:#999;font-weight:600;'
      frag.appendChild(g)
    }
    const addItem = (label, fn) => {
      const b = document.createElement('div')
      b.textContent = label
      b.style.cssText = 'padding:6px 16px;cursor:pointer;color:#333;'
      b.onmouseenter = () => { b.style.background = '#f0f0f0' }
      b.onmouseleave = () => { b.style.background = 'transparent' }
      b.onclick = (e) => { e.stopPropagation(); hideAllMenus(); fn() }
      frag.appendChild(b)
    }
    // 播放一次后回到待机
    const playOnce = (name) => { playAnim(name, false); ui.video.onended = () => playIdle() }

    // 动画池（空池跳过，不显示空分组）
    const groups = [
      ['点击回应', POOLS.clicks],
      ['随机动作', POOLS.random],
      ['时节动作', POOLS.seasonal],
      ['移动', POOLS.moves],
      ['文字梗', POOLS.textMeme],
      ['碎碎念', POOLS.whisper],
    ]
    groups.forEach(([title, pool]) => {
      if (!pool || !pool.length) return
      addSep(); addGroup(title)
      pool.forEach(n => addItem(n, () => playOnce(n)))
    })

    // 表情包
    addSep(); addGroup('表情包')
    Object.keys(MEMES).forEach(name => addItem('🖼 ' + name, () => showBubble(name, 6000, name)))
    return frag
  }

  function openSubmenu(anchor) {
    clearTimeout(submenuHideTimer)
    submenu.innerHTML = ''
    submenu.appendChild(buildSubmenuItems())
    submenu.style.display = 'block'
    const rect = anchor.getBoundingClientRect()
    const subW = submenu.offsetWidth
    const subH = submenu.offsetHeight
    submenu.style.left = Math.min(rect.right + 4, window.innerWidth - subW - 8) + 'px'
    submenu.style.top = Math.max(4, Math.min(rect.top, window.innerHeight - subH - 8)) + 'px'
    submenu.onmouseenter = () => clearTimeout(submenuHideTimer)
    submenu.onmouseleave = () => scheduleSubmenuHide()
  }

  function showMenu(x, y) {
    menu.innerHTML = ''
    submenu.style.display = 'none'
    clearTimeout(submenuHideTimer)

    const addItem = (label, fn) => {
      const b = document.createElement('div')
      b.textContent = label
      b.style.cssText = 'padding:6px 16px;cursor:pointer;color:#333;'
      b.onmouseenter = () => { b.style.background = '#f0f0f0' }
      b.onmouseleave = () => { b.style.background = 'transparent' }
      b.onclick = (e) => { e.stopPropagation(); hideAllMenus(); fn() }
      menu.appendChild(b)
    }
    const addSep = () => {
      const s = document.createElement('div')
      s.style.cssText = 'border-top:1px solid #eee;margin:4px 0'
      menu.appendChild(s)
    }

    // 一级菜单：原有常用项 + 「更多」展开二级
    addItem('💬 跟我说话', () => openChatBox())
    addSep()
    addItem('待机', () => playIdle())
    addItem('随机动作', () => playRandomAction())
    addItem('转身', () => { state.facing *= -1; playAnim(pickRandom(POOLS.turn), false, true) })
    addSep()

    // 工作状态（原一级保留）
    POOLS.workStatus.forEach(n => {
      addItem(n.replace('工作状态-', ''), () => { playAnim(n, false); ui.video.onended = () => playIdle() })
    })
    addSep()

    // 「更多」：悬停或点击展开二级（所有动作 + 表情包）
    const moreBtn = document.createElement('div')
    moreBtn.textContent = '更多'
    moreBtn.style.cssText = 'padding:7px 16px;cursor:pointer;color:#333;display:flex;justify-content:space-between;align-items:center;gap:8px;'
    const arrow = document.createElement('span')
    arrow.textContent = '▶'
    arrow.style.cssText = 'font-size:9px;opacity:0.55;'
    moreBtn.appendChild(arrow)
    moreBtn.onmouseenter = () => { moreBtn.style.background = '#f0f0f0'; openSubmenu(moreBtn) }
    moreBtn.onmouseleave = () => { moreBtn.style.background = 'transparent'; scheduleSubmenuHide() }
    moreBtn.onclick = (e) => { e.stopPropagation(); openSubmenu(moreBtn) }
    menu.appendChild(moreBtn)
    addSep()

    addItem('隐藏', () => hidePet())

    menu.style.display = 'block'
    const menuW = menu.offsetWidth
    const menuH = menu.offsetHeight
    menu.style.left = Math.max(4, Math.min(x, window.innerWidth - menuW - 8)) + 'px'
    menu.style.top = Math.max(4, Math.min(y, window.innerHeight - menuH - 8)) + 'px'
  }

  // ── 事件绑定 ──────────────────────────────────────────
  ui.root.addEventListener('mousedown', onPointerDown)
  document.addEventListener('mousemove', onPointerMove)
  document.addEventListener('mouseup', onPointerUp)
  ui.root.addEventListener('click', onPointerClick)
  ui.root.addEventListener('contextmenu', (e) => {
    e.preventDefault()
    showMenu(e.clientX, e.clientY)
  })
  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && !submenu.contains(e.target)) {
      hideAllMenus()
    }
    const chatBox = document.getElementById('dshp-chatbox')
    if (chatBox && chatBox.style.display !== 'none' && !chatBox.contains(e.target)) {
      chatBox.style.display = 'none'
    }
  })

  // ── 恢复位置 ──────────────────────────────────────────
  function restoreLayout() {
    try {
      const saved = JSON.parse(localStorage.getItem(LS_KEY) || 'null')
      if (saved && saved.left !== undefined) {
        // 钳制在视口内（防止历史坏数据把桌宠拖出屏幕）
        const w = ui.root.offsetWidth
        const h = ui.root.offsetHeight
        const maxX = window.innerWidth - w
        const maxY = window.innerHeight - h
        const left = Math.max(0, Math.min(maxX, saved.left))
        const top = Math.max(0, Math.min(maxY, saved.top))
        ui.root.style.left = left + 'px'
        ui.root.style.top = top + 'px'
        ui.root.style.right = 'auto'
      }
    } catch (e) {}
  }

  // ── 碎碎念（定时随机说话 + 表情包）────────────────────
  const WHISPER_LINES = [
    // 关心 / 问候
    '主人忙不忙呀？', '喝点水休息一下嘛~', '今天也要加油鸭~', '别太累着自己哦',
    '外面天气怎么样呀？', '饿不饿？我给你找点吃的~', '今天有什么有趣的事吗',
    '要不要摸摸头~', '主人最棒啦！', '辛苦啦，我在陪着你呢',
    // 陪伴 / 撒娇
    '喵~想吃点零食', '又在忙呀，我乖乖待着', '写代码好累哦，不过我会陪你',
    '呜…有点无聊，陪我玩会儿嘛', '数据跑完了吗？', '肚子有点饿了…',
    '我给你讲个笑话吧', '要抱抱吗？', '主人，我好像长胖了一点点',
    // 吐槽 / 俏皮
    '这个 bug 是不是又来捣乱了', '代码又在报错啦，要我帮你看看吗',
    '熬夜不好哦，早点休息~', '今天喝了咖啡吗？', '悄悄说，我最喜欢主人了',
    '主人打字好快呀', '要不要我给你唱首歌？', '今天的我也会好好守护主人！',
  ]

  function scheduleWhisper() {
    clearTimeout(state.whisperTimer)
    const delay = CONFIG.whisperMinMs + Math.random() * (CONFIG.whisperMaxMs - CONFIG.whisperMinMs)
    state.whisperTimer = setTimeout(() => {
      if (document.hidden || state.sleeping) { scheduleWhisper(); return }
      doWhisper()
    }, delay)
  }

  function doWhisper() {
    const line = pickRandom(WHISPER_LINES)
    // 按 CONFIG 概率配表情包（宠物没有表情包时 memeNames 为空 → 不配图）
    const memeNames = Object.keys(MEMES)
    const meme = Math.random() < CONFIG.whisperMemeChance ? pickRandom(memeNames) : null
    // 宠物可能没有 whisper 池 → 只有成功播放了非循环动画才挂 onended 回到待机
    const w = pickRandom(POOLS.whisper)
    if (w) {
      playAnim(w, false)
      ui.video.onended = () => { playIdle(); scheduleNextRandom() }
    }
    showBubble(line, CONFIG.whisperBubbleMs, meme)
    scheduleWhisper()
  }

  // ── AI 状态联动（SSE）──────────────────────────────────
  function connectSSE() {
    let es = null
    let retry = 0
    const open = () => {
      es = new EventSource(BASE + '/events')
      es.onopen = () => { retry = 0 }
      es.onmessage = (ev) => {
        let msg
        try { msg = JSON.parse(ev.data) } catch (e) { return }
        handleEvent(msg)
      }
      es.onerror = () => {
        try { es.close() } catch (e) {}
        retry++
        setTimeout(open, Math.min(10000, 800 * retry))
      }
    }
    open()
  }

  function handleEvent(msg) {
    if (!msg || !msg.t) return
    switch (msg.t) {
      case 'hello':
        break
      case 'user':
        playByRole('idle', true)
        showBubble('在听呢～', 2000)
        break
      case 'turn-start':
        playByRole('thinking', true)
        showBubble('让我想想…', 3000)
        break
      case 'tool-call':
        playByRole('working', true)
        showBubble('干活中：' + (msg.name || ''), 2000)
        break
      case 'delta':
        // 输出中：切到待机（若宠物没有专门的 idle 就不动），避免反复重载
        if (state.current == null || state.current.indexOf('工作状态') === 0) {
          playByRole('idle', true)
        }
        break
      case 'turn-end':
        if (msg.status === 'error') {
          playByRole('error', false)
          showBubble('呜…出错了', 2500)
        } else {
          playByRole('success', false)
          showBubble('搞定啦！', 2500)
        }
        ui.video.onended = () => { playIdle(); scheduleNextRandom() }
        break
      case 'say-reply':
        showBubble(msg.text || '', 5000)
        playByRole('idle', true)
        break
      case 'active-message':
        // AI 主动发消息 → 播放碎碎念动画 + 气泡 + 把消息加到主页面
        showBubble(msg.text || '', 6000)
        playByRole('whisper', false)
        ui.video.onended = () => { playIdle(); scheduleNextRandom() }
        // 同步到主页面 chatData（如果存在）
        try {
          if (typeof chatData !== 'undefined' && Array.isArray(chatData)) {
            chatData.push({ role: 'ai', message: msg.text || '', reactions: {} })
          }
        } catch (e) {}
        break
    }
  }

  // ── 对话输入框（反向通道）──────────────────────────────
  function closeChatBox() {
    const box = document.getElementById('dshp-chatbox')
    if (box) box.style.display = 'none'
  }

  function openChatBox() {
    let box = document.getElementById('dshp-chatbox')
    if (box) {
      box.style.display = 'flex'
      const input = box.querySelector('input')
      if (input) input.focus()
      return
    }
    box = document.createElement('div')
    box.id = 'dshp-chatbox'
    box.style.cssText = [
      'position:fixed', 'z-index:2147483002', 'right:24px', 'bottom:120px',
      'background:#fff', 'border-radius:12px', 'box-shadow:0 4px 16px rgba(0,0,0,0.2)',
      'padding:8px', 'display:flex', 'gap:6px', 'align-items:center',
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
    ].join(';')

    const closeBtn = document.createElement('button')
    closeBtn.textContent = '×'
    closeBtn.title = '关闭'
    closeBtn.style.cssText = 'border:none;background:transparent;color:#999;font-size:18px;cursor:pointer;padding:0 4px;line-height:1;'
    closeBtn.onclick = closeChatBox

    const input = document.createElement('input')
    input.type = 'text'
    input.placeholder = '跟她说点什么…'
    input.maxLength = 200
    input.style.cssText = 'border:1px solid #ddd;border-radius:8px;padding:8px 10px;width:200px;font-size:13px;color:#333;outline:none;'
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        const text = input.value.trim()
        if (!text) return
        input.value = ''
        sendToMainChat(text)
      } else if (e.key === 'Escape') {
        closeChatBox()
      }
    })

    const btn = document.createElement('button')
    btn.textContent = '发送'
    btn.style.cssText = 'border:none;background:#7c5cff;color:#fff;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;'
    btn.onclick = () => {
      const text = input.value.trim()
      if (!text) return
      input.value = ''
      sendToMainChat(text)
    }

    box.appendChild(closeBtn)
    box.appendChild(input)
    box.appendChild(btn)
    document.body.appendChild(box)
    input.focus()
  }

  // 桌宠「跟我说话」→ 优先直接发到主对话（走主 chat 完整流程：流式 + 渲染 + 持久化）
  function sendToMainChat(text) {
    // 只有主对话页面存在 #userInput 且暴露全局 sendMessage 时，才走主对话
    const input = document.getElementById('userInput')
    if (input && typeof window.sendMessage === 'function') {
      // 主对话正在输出时避免打断（sendMessage 内部有 isSending 锁会直接丢弃）
      if (typeof window.isSending !== 'undefined' && window.isSending) {
        showBubble('主对话正在回复中，稍等一下～', 3000)
        return
      }
      try {
        // 写入主输入框并触发发送；sendMessage 内部会 addMessage + chatStream + reindex + 持久化
        input.value = text
        input.dispatchEvent(new Event('input'))
        window.sendMessage()
        return
      } catch (e) {
        console.warn('[dsh-pet] 主对话发送失败，回退 /say', e)
      }
    }
    // 不在聊天页（如首页）或主对话不可用 → 回退到桌宠独立通道
    sendSay(text)
  }

  async function sendSay(text) {
    showBubble('…', 5000)
    try {
      // 深绑定：带上当前会话历史 + 登录态，让桌宠走主 chat 的同一套大脑
      const headers = { 'Content-Type': 'application/json' }
      const token = (typeof localStorage !== 'undefined') ? localStorage.getItem('token') : null
      if (token && token !== 'null') headers['Authorization'] = 'Bearer ' + token

      // 读取主页面当前会话历史（chatData 是顶层 let，跨脚本可访问）
      let history = []
      try {
        if (typeof chatData !== 'undefined' && Array.isArray(chatData)) {
          history = chatData
        }
      } catch (e) {}

      const body = {
        text,
        history,
      }
      // 带上主页面的 LLM 自定义配置（若存在）
      try {
        const llmCfg = (typeof getLLMConfig === 'function') ? getLLMConfig() : null
        if (llmCfg) body.llm = llmCfg
      } catch (e) {}

      const res = await fetch(BASE + '/say', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (data.ok && data.reply) {
        showBubble(data.reply, 6000)
        // 把这条对话也同步回主页面 chatData（保持会话历史一致）
        try {
          if (typeof chatData !== 'undefined' && Array.isArray(chatData)) {
            const nowIso = new Date().toISOString()
            chatData.push({ role: 'user', message: text, reactions: {}, created_at: nowIso })
            chatData.push({ role: 'ai', message: data.reply, reactions: {}, created_at: nowIso })
          }
        } catch (e) {}
      } else {
        showBubble('唔…（' + (data.error || '出错了') + '）', 3000)
      }
    } catch (e) {
      showBubble('网络出错啦', 3000)
    }
  }

  // ── 加载后端合并配置（用户资源 + 触发条件）─────────────
  async function loadConfig() {
    try {
      const headers = {}
      const token = (typeof localStorage !== 'undefined') ? localStorage.getItem('token') : null
      if (token && token !== 'null') headers['Authorization'] = 'Bearer ' + token
      const res = await fetch(BASE + '/config', { headers })
      const data = await res.json()
      if (!data) return

      REMOTE_CFG = data

      // 动画池：后端合并结果直接覆盖（含内置 + 用户追加）。
      // 注意：空数组也要覆盖，否则切宠物后空池（如碎碎念/时节）会残留大肥鱼内置动画。
      if (data.pools && typeof data.pools === 'object') {
        Object.keys(POOLS).forEach(k => {
          if (Array.isArray(data.pools[k])) POOLS[k] = data.pools[k]
        })
      }
      // 表情包映射（后端已按当前宠物决定：切宠物后给宠物自带表情包，没有则为空）
      if (data.memes && typeof data.memes === 'object') {
        MEMES = data.memes
      }
      // 当前宠物包自带的表情包名清单（resolveAsset 用它判断去 PET_DIR/memes 取图）
      PET_MEMES = Array.isArray(data.petMemes) ? data.petMemes : []
      // 音效映射
      if (data.sounds && typeof data.sounds === 'object') {
        SOUNDS = Object.assign({}, SOUNDS, data.sounds)
      }
      // 用户资源清单与路径
      if (data.userAssets) {
        USER_ASSETS = data.userAssets
      }
      if (data.userDir) {
        USER_DIR = data.userDir
      }
      // 当前宠物包资源目录（插件市场）
      if (data.petDir) {
        PET_DIR = data.petDir
        // 宠物包动画名 = 当前 pools 里的全部动画（后端已用宠物池覆盖）
        PET_WEBMS = []
        Object.keys(POOLS).forEach(k => {
          if (Array.isArray(POOLS[k])) PET_WEBMS = PET_WEBMS.concat(POOLS[k])
        })
        PET_WEBMS = Array.from(new Set(PET_WEBMS))
      } else {
        PET_DIR = null
        PET_WEBMS = []
      }

      console.log('[dsh-pet] 配置已加载：动画池', Object.keys(POOLS).map(k => k + ':' + POOLS[k].length).join(' '), '| 表情', Object.keys(MEMES).length, '| 音效', Object.keys(SOUNDS).length)
    } catch (e) {
      console.warn('[dsh-pet] 配置加载失败，使用内置默认', e)
    }
  }

  // ── 启动 ──────────────────────────────────────────────
  async function main() {
    restoreLayout()
    await loadConfig()
    playIdle()
    scheduleNextRandom()
    scheduleWhisper()
    connectSSE()
    // 开场白按当前宠物名生成（默认大肥鱼），不再硬编码成某个角色
    const petName = (REMOTE_CFG && REMOTE_CFG.currentPet && REMOTE_CFG.currentPet.name) || '大肥鱼'
    showBubble('🐾 ' + petName + '来啦', 3000)
    console.log('[dsh-pet] 就绪：动画池', Object.keys(POOLS).map(k => k + ':' + POOLS[k].length).join(' '))
  }

  // 修复：浏览器前进/后退（bfcache）恢复页面时，video 会停止/黑屏，
  // 导致桌宠「消失」。这里在恢复时重新播放动画 + 重连 SSE。
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) {
      try {
        // 桌宠 root 若被隐藏（用户手动隐藏），保持隐藏状态，不强行拉出
        if (ui.root.style.display === 'none') return
        playIdle()
        scheduleNextRandom()
        scheduleWhisper()
        connectSSE()
      } catch (err) {}
    }
  })

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', main)
  else main()
})()
