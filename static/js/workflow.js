// ============================================
// 无代码工作流编辑器
// ============================================

const NODE_TYPES = {
    start: { name: '开始', icon: '▶', hasInput: false, hasOutput: true },
    end: { name: '结束', icon: '■', hasInput: true, hasOutput: false },
    ai_chat: { name: 'AI 对话', icon: '🤖', hasInput: true, hasOutput: true },
    code: { name: '代码执行', icon: '🐍', hasInput: true, hasOutput: true },
    template: { name: '场景模板', icon: '📋', hasInput: true, hasOutput: true },
    condition: { name: '条件判断', icon: '❓', hasInput: true, hasOutput: true },
    loop: { name: '循环', icon: '🔄', hasInput: true, hasOutput: true },
    merge: { name: '合并', icon: '🔀', hasInput: true, hasOutput: true },
    user_input: { name: '用户输入', icon: '💬', hasInput: true, hasOutput: true },
};

const DEFAULT_NODE_DATA = {
    start: { name: '开始' },
    end: { name: '结束' },
    ai_chat: { name: 'AI 对话', systemPrompt: '', temperature: 0.7 },
    code: { name: '代码执行', code: '# 在沙箱中执行 Python 代码\n# 上游输入通过 input 变量访问\n# 结果赋值给 result 变量输出\n\nresult = input.upper() if input else "no input"\n' },
    template: { name: '场景模板', scene: '' },
    condition: { name: '条件判断', expression: '' },
    loop: { name: '循环', mode: 'count', count: 3, list: '' },
    merge: { name: '合并', strategy: 'concat' },
    user_input: { name: '用户输入', placeholder: '请输入...' },
};

// 工作流状态
let nodes = [];
let edges = [];
let selectedNodeId = null;
let selectedEdgeId = null;

// DOM 引用
const canvas = document.getElementById('canvas');
const canvasWrap = document.getElementById('canvasWrap');
const edgesSvg = document.getElementById('edgesSvg');
const propEmpty = document.getElementById('propEmpty');
const propContent = document.getElementById('propContent');
const wfTip = document.getElementById('wfTip');

// 生成唯一ID
function uid(prefix = 'node') {
    return prefix + '_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

// 显示提示
function showTip(msg, type = '') {
    wfTip.textContent = msg;
    wfTip.className = 'wf-tip show ' + type;
    setTimeout(() => {
        wfTip.classList.remove('show');
    }, 2000);
}

// ============================================
// 节点渲染
// ============================================
function createCanvasNode(nodeData) {
    const typeInfo = NODE_TYPES[nodeData.type];
    const nodeEl = document.createElement('div');
    nodeEl.className = 'wf-canvas-node';
    nodeEl.dataset.nodeId = nodeData.id;
    nodeEl.dataset.type = nodeData.type;
    nodeEl.style.left = nodeData.x + 'px';
    nodeEl.style.top = nodeData.y + 'px';

    nodeEl.innerHTML = `
        <div class="wf-canvas-node-header">
            <span class="wf-node-status-badge" data-status-badge></span>
            <span class="wf-node-header-icon">${typeInfo.icon}</span>
            <span class="wf-node-header-title">${nodeData.data?.name || typeInfo.name}</span>
            <button class="wf-node-delete-btn" title="删除节点">×</button>
        </div>
        <div class="wf-canvas-node-body">
            ${getNodeBodyPreview(nodeData)}
        </div>
        ${typeInfo.hasInput ? '<div class="wf-node-port input" data-port="input"></div>' : ''}
        ${typeInfo.hasOutput ? '<div class="wf-node-port output" data-port="output"></div>' : ''}
    `;

    // 选中节点
    nodeEl.addEventListener('mousedown', (e) => {
        if (e.target.closest('.wf-node-port') || e.target.closest('.wf-node-delete-btn')) return;
        selectNode(nodeData.id);
        startDragNode(e, nodeEl, nodeData);
    });

    // 删除节点
    nodeEl.querySelector('.wf-node-delete-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteNode(nodeData.id);
    });

    // 连接点事件
    nodeEl.querySelectorAll('.wf-node-port').forEach(port => {
        port.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            startConnect(e, nodeData.id, port.dataset.port);
        });
    });

    return nodeEl;
}

function getNodeBodyPreview(nodeData) {
    const type = nodeData.type;
    const data = nodeData.data || {};
    switch (type) {
        case 'ai_chat':
            return data.systemPrompt ? '系统提示词: ' + data.systemPrompt.slice(0, 30) + (data.systemPrompt.length > 30 ? '...' : '') : '点击配置系统提示词';
        case 'code':
            return data.code ? data.code.split('\n').filter(l => l.trim() && !l.trim().startsWith('#'))[0]?.slice(0, 40) || 'Python 代码' : '点击编辑代码';
        case 'template':
            return data.scene ? '场景: ' + data.scene : '点击选择场景';
        case 'condition':
            return data.expression ? '条件: ' + data.expression.slice(0, 30) : '点击配置条件';
        case 'loop':
            if (data.mode === 'list') {
                const items = (data.list || '').split(',').filter(x => x.trim());
                return `列表循环（${items.length} 项）`;
            }
            return `次数循环（${data.count || 3} 次）`;
        case 'merge':
            const strategyMap = { concat: '拼接', last: '取最新', first: '取最早' };
            return '策略: ' + (strategyMap[data.strategy] || '拼接');
        case 'user_input':
            return data.placeholder ? '提示: ' + data.placeholder : '点击配置提示词';
        default:
            return '';
    }
}

function renderAllNodes() {
    canvas.innerHTML = '';
    nodes.forEach(n => {
        canvas.appendChild(createCanvasNode(n));
    });
    renderAllEdges();
}

// ============================================
// 节点拖拽
// ============================================
let dragState = null;

function startDragNode(e, nodeEl, nodeData) {
    const rect = nodeEl.getBoundingClientRect();
    const canvasRect = canvas.getBoundingClientRect();
    dragState = {
        nodeId: nodeData.id,
        offsetX: e.clientX - rect.left,
        offsetY: e.clientY - rect.top,
    };

    document.addEventListener('mousemove', onDragNode);
    document.addEventListener('mouseup', stopDragNode);
}

function onDragNode(e) {
    if (!dragState) return;
    const canvasRect = canvas.getBoundingClientRect();
    const node = nodes.find(n => n.id === dragState.nodeId);
    if (!node) return;

    node.x = Math.max(0, e.clientX - canvasRect.left - dragState.offsetX);
    node.y = Math.max(0, e.clientY - canvasRect.top - dragState.offsetY);

    const nodeEl = canvas.querySelector(`[data-node-id="${node.id}"]`);
    if (nodeEl) {
        nodeEl.style.left = node.x + 'px';
        nodeEl.style.top = node.y + 'px';
    }
    renderAllEdges();
}

function stopDragNode() {
    dragState = null;
    document.removeEventListener('mousemove', onDragNode);
    document.removeEventListener('mouseup', stopDragNode);
}

// ============================================
// 连接节点（连线）
// ============================================
let connectState = null;

function startConnect(e, nodeId, portType) {
    connectState = {
        sourceNodeId: nodeId,
        sourcePort: portType,
        tempLine: null,
    };
    document.addEventListener('mousemove', onConnecting);
    document.addEventListener('mouseup', stopConnect);
}

function onConnecting(e) {
    if (!connectState) return;
    const canvasRect = canvas.getBoundingClientRect();
    const sourceNode = nodes.find(n => n.id === connectState.sourceNodeId);
    const sourceEl = canvas.querySelector(`[data-node-id="${sourceNode.id}"]`);
    if (!sourceEl) return;

    const startPos = getPortPosition(sourceEl, connectState.sourcePort);
    const endX = e.clientX - canvasRect.left;
    const endY = e.clientY - canvasRect.top;

    if (!connectState.tempLine) {
        connectState.tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        connectState.tempLine.setAttribute('class', 'wf-edge');
        connectState.tempLine.setAttribute('stroke-dasharray', '5,5');
        edgesSvg.appendChild(connectState.tempLine);
    }
    connectState.tempLine.setAttribute('d', buildBezierPath(startPos.x, startPos.y, endX, endY));
}

function stopConnect(e) {
    if (connectState?.tempLine) {
        connectState.tempLine.remove();
    }

    // 检查是否连接到有效端口
    const target = document.elementFromPoint(e.clientX, e.clientY);
    if (target?.classList.contains('wf-node-port')) {
        const targetNodeEl = target.closest('.wf-canvas-node');
        const targetNodeId = targetNodeEl?.dataset.nodeId;
        const targetPort = target.dataset.port;

        if (targetNodeId && targetNodeId !== connectState.sourceNodeId) {
            // 必须是 output -> input
            if (connectState.sourcePort === 'output' && targetPort === 'input') {
                addEdge(connectState.sourceNodeId, targetNodeId);
            } else if (connectState.sourcePort === 'input' && targetPort === 'output') {
                addEdge(targetNodeId, connectState.sourceNodeId);
            }
        }
    }

    connectState = null;
    document.removeEventListener('mousemove', onConnecting);
    document.removeEventListener('mouseup', stopConnect);
}

function getPortPosition(nodeEl, portType) {
    const nodeRect = nodeEl.getBoundingClientRect();
    const canvasRect = canvas.getBoundingClientRect();
    if (portType === 'input') {
        return {
            x: nodeRect.left - canvasRect.left,
            y: nodeRect.top - canvasRect.top + nodeRect.height / 2,
        };
    } else {
        return {
            x: nodeRect.left - canvasRect.left + nodeRect.width,
            y: nodeRect.top - canvasRect.top + nodeRect.height / 2,
        };
    }
}

function buildBezierPath(x1, y1, x2, y2) {
    const dx = Math.abs(x2 - x1) * 0.5;
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

function addEdge(sourceId, targetId) {
    // 避免重复连线
    if (edges.some(e => e.source === sourceId && e.target === targetId)) return;
    const edge = { id: uid('edge'), source: sourceId, target: targetId };
    edges.push(edge);
    renderAllEdges();
}

function renderAllEdges() {
    // 清除旧连线（保留defs）
    edgesSvg.querySelectorAll('.wf-edge').forEach(el => el.remove());

    edges.forEach(edge => {
        const sourceEl = canvas.querySelector(`[data-node-id="${edge.source}"]`);
        const targetEl = canvas.querySelector(`[data-node-id="${edge.target}"]`);
        if (!sourceEl || !targetEl) return;

        const start = getPortPosition(sourceEl, 'output');
        const end = getPortPosition(targetEl, 'input');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', 'wf-edge' + (selectedEdgeId === edge.id ? ' selected' : ''));
        path.setAttribute('d', buildBezierPath(start.x, start.y, end.x, end.y));
        path.setAttribute('marker-end', 'url(#arrowhead)');
        path.dataset.edgeId = edge.id;

        path.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm('删除这条连线？')) {
                deleteEdge(edge.id);
            }
        });

        edgesSvg.appendChild(path);
    });
}

function deleteEdge(edgeId) {
    edges = edges.filter(e => e.id !== edgeId);
    if (selectedEdgeId === edgeId) selectedEdgeId = null;
    renderAllEdges();
}

// ============================================
// 选中 / 删除节点
// ============================================
function selectNode(nodeId) {
    selectedNodeId = nodeId;
    selectedEdgeId = null;
    canvas.querySelectorAll('.wf-canvas-node').forEach(el => {
        el.classList.toggle('selected', el.dataset.nodeId === nodeId);
    });
    renderPropertyPanel();
}

function deselectAll() {
    selectedNodeId = null;
    selectedEdgeId = null;
    canvas.querySelectorAll('.wf-canvas-node').forEach(el => el.classList.remove('selected'));
    edgesSvg.querySelectorAll('.wf-edge').forEach(el => el.classList.remove('selected'));
    renderPropertyPanel();
}

function deleteNode(nodeId) {
    if (!confirm('删除这个节点？相关连线也会被删除。')) return;
    nodes = nodes.filter(n => n.id !== nodeId);
    edges = edges.filter(e => e.source !== nodeId && e.target !== nodeId);
    if (selectedNodeId === nodeId) deselectAll();
    renderAllNodes();
}

// ============================================
// 属性面板
// ============================================
function renderPropertyPanel() {
    const node = nodes.find(n => n.id === selectedNodeId);
    if (!node) {
        propEmpty.hidden = false;
        propContent.hidden = true;
        return;
    }
    propEmpty.hidden = true;
    propContent.hidden = false;

    const typeInfo = NODE_TYPES[node.type];
    const data = node.data || {};
    let html = `
        <div class="wf-prop-group">
            <div class="wf-prop-label">节点名称</div>
            <input type="text" class="wf-prop-input" id="propName" value="${data.name || typeInfo.name}">
        </div>
    `;

    switch (node.type) {
        case 'ai_chat':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">系统提示词</div>
                    <textarea class="wf-prop-textarea" id="propSystemPrompt" placeholder="定义AI的角色和行为...">${data.systemPrompt || ''}</textarea>
                </div>
                <div class="wf-prop-group">
                    <div class="wf-prop-label">Temperature (0-1)</div>
                    <input type="number" class="wf-prop-input" id="propTemp" value="${data.temperature ?? 0.7}" min="0" max="1" step="0.1">
                </div>
            `;
            break;
        case 'code':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">Python 代码</div>
                    <div class="wf-prop-hint">通过 <code>input</code> 访问上游输入，将结果赋值给 <code>result</code> 输出</div>
                    <textarea class="wf-prop-textarea wf-code-editor" id="propCode" spellcheck="false" placeholder="# 例如：计算阶乘&#10;def fact(n):&#10;    return 1 if n &lt;= 1 else n * fact(n-1)&#10;result = fact(int(input) if input else 5)">${data.code || ''}</textarea>
                </div>
            `;
            break;
        case 'template':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">选择场景</div>
                    <select class="wf-prop-select" id="propScene">
                        <option value="">通用模式</option>
                        <option value="chat" ${data.scene === 'chat' ? 'selected' : ''}>日常闲聊</option>
                        <option value="office" ${data.scene === 'office' ? 'selected' : ''}>办公文案</option>
                        <option value="study" ${data.scene === 'study' ? 'selected' : ''}>学习答疑</option>
                        <option value="life" ${data.scene === 'life' ? 'selected' : ''}>生活解惑</option>
                    </select>
                </div>
            `;
            break;
        case 'condition':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">条件表达式</div>
                    <textarea class="wf-prop-textarea" id="propExpression" placeholder="例如: input.includes('你好')">${data.expression || ''}</textarea>
                </div>
            `;
            break;
        case 'user_input':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">输入提示</div>
                    <input type="text" class="wf-prop-input" id="propPlaceholder" value="${data.placeholder || ''}" placeholder="请输入...">
                </div>
            `;
            break;
        case 'loop':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">循环模式</div>
                    <select class="wf-prop-select" id="propLoopMode">
                        <option value="count" ${data.mode === 'count' ? 'selected' : ''}>按次数</option>
                        <option value="list" ${data.mode === 'list' ? 'selected' : ''}>按列表</option>
                    </select>
                </div>
                <div class="wf-prop-group" id="propLoopCountGroup">
                    <div class="wf-prop-label">循环次数</div>
                    <input type="number" class="wf-prop-input" id="propLoopCount" value="${data.count ?? 3}" min="1" max="100">
                </div>
                <div class="wf-prop-group" id="propLoopListGroup" style="display:${data.mode === 'list' ? 'block' : 'none'}">
                    <div class="wf-prop-label">列表项（逗号分隔）</div>
                    <textarea class="wf-prop-textarea" id="propLoopList" placeholder="例如：苹果,香蕉,橙子">${data.list || ''}</textarea>
                </div>
            `;
            break;
        case 'merge':
            html += `
                <div class="wf-prop-group">
                    <div class="wf-prop-label">合并策略</div>
                    <select class="wf-prop-select" id="propMergeStrategy">
                        <option value="concat" ${data.strategy === 'concat' ? 'selected' : ''}>拼接（用分隔线连接）</option>
                        <option value="last" ${data.strategy === 'last' ? 'selected' : ''}>取最新输入</option>
                        <option value="first" ${data.strategy === 'first' ? 'selected' : ''}>取最早输入</option>
                    </select>
                </div>
            `;
            break;
    }

    propContent.innerHTML = html;

    // 绑定修改事件
    document.getElementById('propName')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { name: e.target.value });
    });
    document.getElementById('propSystemPrompt')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { systemPrompt: e.target.value });
    });
    document.getElementById('propTemp')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { temperature: parseFloat(e.target.value) });
    });
    document.getElementById('propCode')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { code: e.target.value });
    });
    document.getElementById('propScene')?.addEventListener('change', (e) => {
        updateNodeData(node.id, { scene: e.target.value });
    });
    document.getElementById('propExpression')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { expression: e.target.value });
    });
    document.getElementById('propPlaceholder')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { placeholder: e.target.value });
    });
    document.getElementById('propLoopMode')?.addEventListener('change', (e) => {
        const mode = e.target.value;
        updateNodeData(node.id, { mode });
        document.getElementById('propLoopCountGroup').style.display = mode === 'count' ? 'block' : 'none';
        document.getElementById('propLoopListGroup').style.display = mode === 'list' ? 'block' : 'none';
    });
    document.getElementById('propLoopCount')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { count: parseInt(e.target.value) || 1 });
    });
    document.getElementById('propLoopList')?.addEventListener('input', (e) => {
        updateNodeData(node.id, { list: e.target.value });
    });
    document.getElementById('propMergeStrategy')?.addEventListener('change', (e) => {
        updateNodeData(node.id, { strategy: e.target.value });
    });
}

function updateNodeData(nodeId, patch) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;
    node.data = { ...node.data, ...patch };

    // 更新节点显示
    const nodeEl = canvas.querySelector(`[data-node-id="${nodeId}"]`);
    if (nodeEl) {
        const titleEl = nodeEl.querySelector('.wf-node-header-title');
        if (titleEl) titleEl.textContent = node.data.name || NODE_TYPES[node.type].name;
        const bodyEl = nodeEl.querySelector('.wf-canvas-node-body');
        if (bodyEl) bodyEl.textContent = getNodeBodyPreview(node);
    }
}

// ============================================
// 从左侧面板拖拽节点到画布
// ============================================
document.querySelectorAll('.wf-node-item').forEach(item => {
    item.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('nodeType', item.dataset.type);
    });
});

canvasWrap.addEventListener('dragover', (e) => {
    e.preventDefault();
});

canvasWrap.addEventListener('drop', (e) => {
    e.preventDefault();
    const nodeType = e.dataTransfer.getData('nodeType');
    if (!nodeType || !NODE_TYPES[nodeType]) return;

    const canvasRect = canvas.getBoundingClientRect();
    const x = e.clientX - canvasRect.left - 90;
    const y = e.clientY - canvasRect.top - 30;

    addNode(nodeType, x, y);
});

function addNode(type, x, y) {
    const node = {
        id: uid('node'),
        type: type,
        x: Math.max(0, x),
        y: Math.max(0, y),
        data: { ...DEFAULT_NODE_DATA[type] },
    };
    nodes.push(node);
    canvas.appendChild(createCanvasNode(node));
    selectNode(node.id);
}

// ============================================
// 工作流模板库
// ============================================
const WORKFLOW_TEMPLATES = [
    {
        id: 'simple_chat',
        name: '简单 AI 对话',
        desc: '最基础的工作流：开始 → AI对话 → 结束',
        icon: '💬',
        build: () => {
            const s = { id: uid('node'), type: 'start', x: 80, y: 150, data: { name: '开始' } };
            const a = { id: uid('node'), type: 'ai_chat', x: 320, y: 150, data: { name: 'AI 对话', systemPrompt: '你是Jingent AI，一位专业的AI助手。', temperature: 0.7 } };
            const e = { id: uid('node'), type: 'end', x: 580, y: 150, data: { name: '结束' } };
            return {
                name: '简单 AI 对话',
                nodes: [s, a, e],
                edges: [
                    { id: uid('edge'), source: s.id, target: a.id },
                    { id: uid('edge'), source: a.id, target: e.id },
                ],
            };
        },
    },
    {
        id: 'branch_chat',
        name: '条件分支对话',
        desc: '根据输入内容判断走不同分支',
        icon: '🔀',
        build: () => {
            const s = { id: uid('node'), type: 'start', x: 60, y: 180, data: { name: '开始' } };
            const c = { id: uid('node'), type: 'condition', x: 280, y: 180, data: { name: '是否中文', expression: 'input.match(/[\\u4e00-\\u9fa5]/)' } };
            const a1 = { id: uid('node'), type: 'ai_chat', x: 520, y: 80, data: { name: '中文助手', systemPrompt: '你是一位中文AI助手，用中文回答问题。', temperature: 0.7 } };
            const a2 = { id: uid('node'), type: 'ai_chat', x: 520, y: 280, data: { name: 'English Assistant', systemPrompt: 'You are a helpful AI assistant. Answer in English.', temperature: 0.7 } };
            const m = { id: uid('node'), type: 'merge', x: 780, y: 180, data: { name: '合并', strategy: 'last' } };
            const e = { id: uid('node'), type: 'end', x: 1000, y: 180, data: { name: '结束' } };
            return {
                name: '条件分支对话',
                nodes: [s, c, a1, a2, m, e],
                edges: [
                    { id: uid('edge'), source: s.id, target: c.id },
                    { id: uid('edge'), source: c.id, target: a1.id },
                    { id: uid('edge'), source: c.id, target: a2.id },
                    { id: uid('edge'), source: a1.id, target: m.id },
                    { id: uid('edge'), source: a2.id, target: m.id },
                    { id: uid('edge'), source: m.id, target: e.id },
                ],
            };
        },
    },
    {
        id: 'loop_review',
        name: '循环润色文案',
        desc: '对多个文案条目依次进行 AI 润色',
        icon: '🔄',
        build: () => {
            const s = { id: uid('node'), type: 'start', x: 60, y: 180, data: { name: '开始' } };
            const l = { id: uid('node'), type: 'loop', x: 280, y: 180, data: { name: '循环处理', mode: 'list', count: 3, list: '请帮我优化这句话,把这段文案改得更吸引人,帮我写得更简洁' } };
            const a = { id: uid('node'), type: 'ai_chat', x: 520, y: 180, data: { name: 'AI 润色', systemPrompt: '你是一位资深文案编辑，负责润色用户提供的文案，让它更有吸引力、更专业。请直接输出润色后的内容。', temperature: 0.8 } };
            const e = { id: uid('node'), type: 'end', x: 780, y: 180, data: { name: '结束' } };
            return {
                name: '循环润色文案',
                nodes: [s, l, a, e],
                edges: [
                    { id: uid('edge'), source: s.id, target: l.id },
                    { id: uid('edge'), source: l.id, target: a.id },
                    { id: uid('edge'), source: a.id, target: e.id },
                ],
            };
        },
    },
    {
        id: 'multi_scene',
        name: '多场景流水线',
        desc: '依次经过日常闲聊→办公文案→学习答疑三种场景处理',
        icon: '📋',
        build: () => {
            const s = { id: uid('node'), type: 'start', x: 60, y: 150, data: { name: '开始' } };
            const t1 = { id: uid('node'), type: 'template', x: 260, y: 150, data: { name: '日常闲聊', scene: 'chat' } };
            const a1 = { id: uid('node'), type: 'ai_chat', x: 460, y: 150, data: { name: '闲聊回复', systemPrompt: '', temperature: 0.9 } };
            const t2 = { id: uid('node'), type: 'template', x: 660, y: 150, data: { name: '办公文案', scene: 'office' } };
            const a2 = { id: uid('node'), type: 'ai_chat', x: 860, y: 150, data: { name: '办公润色', systemPrompt: '', temperature: 0.7 } };
            const e = { id: uid('node'), type: 'end', x: 1060, y: 150, data: { name: '结束' } };
            return {
                name: '多场景流水线',
                nodes: [s, t1, a1, t2, a2, e],
                edges: [
                    { id: uid('edge'), source: s.id, target: t1.id },
                    { id: uid('edge'), source: t1.id, target: a1.id },
                    { id: uid('edge'), source: a1.id, target: t2.id },
                    { id: uid('edge'), source: t2.id, target: a2.id },
                    { id: uid('edge'), source: a2.id, target: e.id },
                ],
            };
        },
    },
];

function buildTemplateLibUI() {
    const overlay = document.createElement('div');
    overlay.className = 'wf-modal-overlay';
    overlay.id = 'templateLibModal';
    overlay.innerHTML = `
        <div class="wf-modal wf-tpl-modal">
            <div class="wf-modal-title">工作流模板库</div>
            <div class="wf-modal-desc">选择一个预设模板，快速创建工作流</div>
            <div class="wf-tpl-grid" id="tplGrid"></div>
            <div class="wf-modal-actions">
                <button class="wf-modal-btn" id="tplCloseBtn">关闭</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // 渲染模板卡片
    const grid = overlay.querySelector('#tplGrid');
    WORKFLOW_TEMPLATES.forEach(tpl => {
        const card = document.createElement('div');
        card.className = 'wf-tpl-card';
        card.innerHTML = `
            <div class="wf-tpl-icon">${tpl.icon}</div>
            <div class="wf-tpl-name">${tpl.name}</div>
            <div class="wf-tpl-desc">${tpl.desc}</div>
            <button class="wf-tpl-use-btn">使用模板</button>
        `;
        card.querySelector('.wf-tpl-use-btn').addEventListener('click', () => {
            useTemplate(tpl);
            closeTemplateLib();
        });
        grid.appendChild(card);
    });

    overlay.querySelector('#tplCloseBtn').addEventListener('click', closeTemplateLib);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeTemplateLib();
    });
}

function openTemplateLib() {
    const m = document.getElementById('templateLibModal');
    if (m) m.classList.add('show');
}

function closeTemplateLib() {
    const m = document.getElementById('templateLibModal');
    if (m) m.classList.remove('show');
}

function useTemplate(tpl) {
    if (nodes.length && !confirm('当前画布内容会被清空，确定使用模板？')) return;

    const data = tpl.build();
    document.getElementById('workflowName').value = data.name;
    nodes = data.nodes;
    edges = data.edges;
    deselectAll();
    renderAllNodes();
    showTip(`已载入模板：${tpl.name}`, 'success');
}

// ============================================
// 工具栏按钮
// ============================================
document.getElementById('templateLibBtn').addEventListener('click', () => {
    openTemplateLib();
});

document.getElementById('clearBtn').addEventListener('click', () => {
    if (!nodes.length && !edges.length) return;
    if (!confirm('确定清空画布？所有节点和连线都会被删除。')) return;
    nodes = [];
    edges = [];
    deselectAll();
    renderAllNodes();
    showTip('画布已清空');
});

document.getElementById('saveBtn').addEventListener('click', () => {
    const name = document.getElementById('workflowName').value.trim() || '未命名工作流';
    const data = { name, nodes, edges, savedAt: Date.now() };
    localStorage.setItem('workflow_current', JSON.stringify(data));
    // 也保存到列表
    const savedList = JSON.parse(localStorage.getItem('workflow_list') || '[]');
    const existingIdx = savedList.findIndex(w => w.name === name);
    if (existingIdx >= 0) {
        savedList[existingIdx] = data;
    } else {
        savedList.push(data);
    }
    localStorage.setItem('workflow_list', JSON.stringify(savedList));
    showTip('工作流已保存', 'success');
});

document.getElementById('runBtn').addEventListener('click', () => {
    if (!nodes.length) {
        showTip('请先添加节点', 'error');
        return;
    }
    const startNodes = nodes.filter(n => n.type === 'start');
    if (!startNodes.length) {
        showTip('缺少「开始」节点', 'error');
        return;
    }
    // 打开初始输入弹窗
    openInputModal();
});

// ============================================
// 执行相关：初始输入弹窗 + 执行日志
// ============================================
function buildExecUI() {
    // 初始输入弹窗
    const modalOverlay = document.createElement('div');
    modalOverlay.className = 'wf-modal-overlay';
    modalOverlay.id = 'inputModal';
    modalOverlay.innerHTML = `
        <div class="wf-modal">
            <div class="wf-modal-title">输入初始数据</div>
            <div class="wf-modal-desc">这些内容会作为「开始」节点的输出，传递给工作流的第一个处理节点。</div>
            <textarea class="wf-modal-textarea" id="initialInput" placeholder="请输入初始内容，例如：一段需要处理的文字、一个问题..."></textarea>
            <div class="wf-modal-actions">
                <button class="wf-modal-btn" id="cancelRunBtn">取消</button>
                <button class="wf-modal-btn wf-modal-btn-primary" id="confirmRunBtn">开始执行</button>
            </div>
        </div>
    `;
    document.body.appendChild(modalOverlay);

    // 执行日志面板
    const execPanel = document.createElement('div');
    execPanel.className = 'wf-exec-panel';
    execPanel.id = 'execPanel';
    execPanel.innerHTML = `
        <div class="wf-exec-header">
            <span class="wf-exec-title">执行日志</span>
            <button class="wf-exec-close" id="execCloseBtn" title="关闭">×</button>
        </div>
        <div class="wf-exec-log" id="execLog"></div>
    `;
    document.body.appendChild(execPanel);

    // 绑定事件
    document.getElementById('cancelRunBtn').addEventListener('click', closeInputModal);
    document.getElementById('confirmRunBtn').addEventListener('click', () => {
        const input = document.getElementById('initialInput').value;
        closeInputModal();
        runWorkflow(input);
    });
    document.getElementById('execCloseBtn').addEventListener('click', () => {
        document.getElementById('execPanel').classList.remove('open');
    });
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) closeInputModal();
    });
}

function openInputModal() {
    const m = document.getElementById('inputModal');
    if (m) m.classList.add('show');
}

function closeInputModal() {
    const m = document.getElementById('inputModal');
    if (m) m.classList.remove('show');
}

function clearNodeStatus() {
    document.querySelectorAll('.wf-canvas-node').forEach(el => {
        el.classList.remove('status-running', 'status-success', 'status-error', 'status-waiting');
        const badge = el.querySelector('[data-status-badge]');
        if (badge) badge.textContent = '';
    });
}

function setNodeStatus(nodeId, status) {
    const el = document.querySelector(`.wf-canvas-node[data-node-id="${nodeId}"]`);
    if (!el) return;
    el.classList.remove('status-running', 'status-success', 'status-error', 'status-waiting');
    el.classList.add('status-' + status);
    const badge = el.querySelector('[data-status-badge]');
    if (badge) {
        const icons = { success: '✓', error: '✕', running: '●', waiting: '◷' };
        badge.textContent = icons[status] || '';
    }
}

function appendExecLog(log) {
    const logContainer = document.getElementById('execLog');
    if (!logContainer) return;
    document.getElementById('execPanel').classList.add('open');

    const item = document.createElement('div');
    item.className = 'wf-log-item';
    const statusText = { success: '成功', error: '失败', running: '执行中', waiting: '等待' };
    item.innerHTML = `
        <span class="wf-log-status ${log.status}">${statusText[log.status] || log.status}</span>
        <div class="wf-log-msg">
            <div>${log.message || ''}</div>
            ${log.output ? `<div class="wf-log-output">${log.output.slice(0, 200)}${log.output.length > 200 ? '...' : ''}</div>` : ''}
        </div>
    `;
    logContainer.appendChild(item);
    logContainer.scrollTop = logContainer.scrollHeight;
}

async function runWorkflow(initialInput) {
    clearNodeStatus();
    const logContainer = document.getElementById('execLog');
    if (logContainer) logContainer.innerHTML = '';
    document.getElementById('execPanel').classList.add('open');

    const name = document.getElementById('workflowName').value.trim() || '未命名工作流';
    showTip('正在执行工作流...');

    try {
        const resp = await fetch('/ai/workflow/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                nodes: nodes.map(n => ({
                    id: n.id, type: n.type, x: n.x, y: n.y, data: n.data || {}
                })),
                edges: edges.map(e => ({ id: e.id, source: e.source, target: e.target })),
                initial_input: initialInput,
            }),
        });
        const result = await resp.json();

        if (result.execution_log) {
            result.execution_log.forEach(log => {
                setNodeStatus(log.node_id, log.status);
                appendExecLog(log);
            });
        }

        if (result.code === 200) {
            showTip('执行完成', 'success');
            if (result.final_output) {
                appendExecLog({
                    node_id: 'final',
                    status: 'success',
                    message: '最终输出结果',
                    output: result.final_output,
                });
            }
        } else if (result.code === 202) {
            showTip('等待用户输入', 'success');
        } else {
            showTip(result.msg || '执行失败', 'error');
        }
    } catch (err) {
        console.error(err);
        showTip('执行出错：' + err.message, 'error');
        appendExecLog({
            node_id: 'error',
            status: 'error',
            message: '网络异常或服务端错误',
            output: err.message,
        });
    }
}

document.getElementById('workflowName').addEventListener('change', () => {
    // 名称变化时自动保存标题
});

// ============================================
// 画布点击取消选中 / 删除
// ============================================
canvas.addEventListener('mousedown', (e) => {
    if (e.target === canvas || e.target === canvasWrap) {
        deselectAll();
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedNodeId && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
            deleteNode(selectedNodeId);
        }
    }
    if (e.key === 'Escape') {
        deselectAll();
    }
});

// ============================================
// 初始化
// ============================================
function initWorkflow() {
    // 构建执行相关UI
    buildExecUI();
    // 构建模板库UI
    buildTemplateLibUI();

    // 尝试加载上次的工作流
    const saved = localStorage.getItem('workflow_current');
    if (saved) {
        try {
            const data = JSON.parse(saved);
            document.getElementById('workflowName').value = data.name || '未命名工作流';
            nodes = data.nodes || [];
            edges = data.edges || [];
        } catch (e) {
            nodes = [];
            edges = [];
        }
    }

    // 如果为空，添加默认开始/结束节点
    if (!nodes.length) {
        addNode('start', 100, 150);
        addNode('end', 500, 150);
    } else {
        renderAllNodes();
    }
    deselectAll();
}

initWorkflow();
