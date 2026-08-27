/* ═══════════════ Genio — Interactive App ═══════════════ */

// ── GitHub Stats ──
async function fetchGitHubStats() {
  try {
    const resp = await fetch('https://api.github.com/repos/HiTechLabTN/genio');
    if (!resp.ok) return;
    const data = await resp.json();
    document.getElementById('gh-star-count').textContent = data.stargazers_count || '—';
    document.getElementById('gh-fork-count').textContent = data.forks_count || '—';
  } catch (e) {
    console.log('GitHub API unavailable');
  }
}

// ── Terminal Typing Effect ──
function typeTerminal() {
  const output = document.getElementById('terminal-output');
  if (!output) return;
  const lines = [
    { text: '📋 Plan ready (deterministic_v4): 8 nodes', cls: 'text-gray-400', delay: 0 },
    { text: '▶️  [sandbox] env_check', cls: 'text-neon-cyan', delay: 400 },
    { text: '✅ env_check (0s) -> Docker=OK, ffmpeg=OK', cls: 'text-gray-400', delay: 800 },
    { text: '▶️  [content] generate_darija_lab', cls: 'text-neon-cyan', delay: 1200 },
    { text: '✅ content (120s) -> 2346 words, SVG=LLM, 4 passes', cls: 'text-gray-400', delay: 2400 },
    { text: '▶️  [media] livetest_recording', cls: 'text-neon-cyan', delay: 3000 },
    { text: '✅ livetest_recording (496s) -> video 112.9s', cls: 'text-gray-400', delay: 4000 },
    { text: '✅ audit -> quality=90/100 security=100/100', cls: 'text-gray-400', delay: 4500 },
    { text: '✅ youtube -> payload generated', cls: 'text-gray-400', delay: 5000 },
    { text: 'ALL 8/8 NODES PASSED', cls: 'text-neon-green font-bold', delay: 5500 },
  ];

  output.innerHTML = '';
  lines.forEach(({ text, cls, delay }) => {
    setTimeout(() => {
      const div = document.createElement('div');
      div.className = cls;
      div.textContent = text;
      output.appendChild(div);
      output.scrollTop = output.scrollHeight;
    }, delay);
  });
}

// ── Playground: Pipeline Execution ──
let ws = null;
let timerInterval = null;
let startTime = null;

const DAG_NODES = [
  { id: 'env_check', label: 'Env', icon: '🔍' },
  { id: 'content', label: 'Content', icon: '📝' },
  { id: 'livetest_recording', label: 'Video', icon: '🎬' },
  { id: 'audio', label: 'Audio', icon: '🔊' },
  { id: 'cover', label: 'Cover', icon: '🖼️' },
  { id: 'audit', label: 'Audit', icon: '✅' },
  { id: 'publish', label: 'Publish', icon: '📡' },
  { id: 'youtube', label: 'YouTube', icon: '▶️' },
];

function renderDAG() {
  const container = document.getElementById('dag-nodes');
  container.innerHTML = DAG_NODES.map(n => `
    <div id="dag-${n.id}" class="dag-node pending px-4 py-2 rounded-lg border border-white/10 bg-dark-900/50 text-xs font-mono flex items-center gap-2">
      <span>${n.icon}</span>
      <span>${n.label}</span>
      <span class="dag-status text-gray-600">⏳</span>
    </div>
  `).join('');
  document.getElementById('dag-container').classList.remove('hidden');
}

function updateDAGNode(id, status) {
  const el = document.getElementById(`dag-${id}`);
  if (!el) return;
  el.className = el.className.replace(/pending|running|success|failed/g, '').trim();
  el.classList.add(status);
  const statusEl = el.querySelector('.dag-status');
  if (statusEl) {
    statusEl.textContent = status === 'success' ? '✅' : status === 'failed' ? '❌' : status === 'running' ? '🔄' : '⏳';
  }
}

function addLog(text, cls = '') {
  const terminal = document.getElementById('log-terminal');
  const div = document.createElement('div');
  div.className = `log-entry ${cls}`;
  const time = startTime ? `[${formatTime(Date.now() - startTime)}]` : '';
  div.textContent = `${time} ${text}`;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

function formatTime(ms) {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function startTimer() {
  startTime = Date.now();
  timerInterval = setInterval(() => {
    document.getElementById('log-timer').textContent = formatTime(Date.now() - startTime);
  }, 1000);
}

function stopTimer() {
  clearInterval(timerInterval);
}

async function runPipeline() {
  const input = document.getElementById('prompt-input');
  const prompt = input.value.trim();
  if (!prompt) { input.focus(); return; }

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.classList.add('opacity-50');
  document.getElementById('run-label').textContent = 'Running...';
  document.getElementById('log-dot').classList.add('animate-pulse');
  document.getElementById('log-status').textContent = 'Executing pipeline...';

  renderDAG();
  document.getElementById('log-terminal').innerHTML = '';
  document.getElementById('artifacts').classList.add('hidden');
  startTimer();

  addLog(`$ genio --auto --prompt "${prompt}"`, 'text-neon-green');
  addLog('📋 Building autonomous DAG...', 'log-info');

  try {
    const resp = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, auto: true, publish: false }),
    });

    const data = await resp.json();

    if (data.results) {
      for (const [nodeId, result] of Object.entries(data.results)) {
        updateDAGNode(nodeId, result.ok ? 'success' : 'failed');
        if (result.output) addLog(`✅ ${nodeId}: ${result.output}`, result.ok ? 'log-success' : 'log-error');
        if (result.error) addLog(`❌ ${nodeId}: ${result.error}`, 'log-error');
      }
    }

    if (data.report) {
      addLog('', '');
      addLog('═══ EXECUTIVE REPORT ═══', 'text-neon-green font-bold');
      const reportLines = data.report.split('\n').slice(0, 15);
      reportLines.forEach(line => addLog(line, 'text-gray-400'));
    }

    document.getElementById('log-status').textContent = 'Pipeline complete';
    document.getElementById('log-dot').classList.remove('animate-pulse');
    document.getElementById('log-dot').classList.add('bg-neon-green');

  } catch (err) {
    addLog(`❌ Error: ${err.message}`, 'log-error');
    document.getElementById('log-status').textContent = 'Error occurred';
  }

  stopTimer();
  btn.disabled = false;
  btn.classList.remove('opacity-50');
  document.getElementById('run-label').textContent = 'Run Pipeline';
}

// ── Code Copy ──
function copyCode(btn) {
  const code = btn.parentElement.querySelector('code');
  navigator.clipboard.writeText(code.textContent).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 2000);
  });
}

// ── Smooth scroll for nav ──
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(a.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

// ── Navbar scroll effect ──
let lastScroll = 0;
window.addEventListener('scroll', () => {
  const navbar = document.getElementById('navbar');
  const scroll = window.scrollY;
  if (scroll > 100) {
    navbar.classList.add('shadow-lg', 'shadow-black/20');
  } else {
    navbar.classList.remove('shadow-lg', 'shadow-black/20');
  }
  lastScroll = scroll;
});

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  fetchGitHubStats();
  setTimeout(typeTerminal, 1000);
  // Refresh GitHub stats every 5 minutes
  setInterval(fetchGitHubStats, 300000);
});
