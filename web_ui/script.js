/**
 * POLYGON BEATER — AI Assistant Voice CS
 * Frontend Client Controller (script.js)
 * 100% Vanilla JavaScript, bez externích závislostí, optimalizováno pro lokální offline běh.
 */

(() => {
  'use strict';

  // ===========================================================================
  // GLOBÁLNÍ STAV KLIENTA
  // ===========================================================================
  const state = {
    sessionId: null,
    sessions: [],
    isStreaming: false,
    abortController: null,
    selectSessionSeq: 0,
    selectSessionAbortController: null,
    attachedFile: null,
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    transcriptionAbortController: null,
    
    // Toggles
    onlineMode: true,
    ragEnabled: true,
    ttsEnabled: false,
    selectedPreset: 'Vypnuto (Standardní chat)',
    
    // Blender polling
    blenderConnected: false,
    blenderPollInterval: null,
  };

  // ===========================================================================
  // DOM ELEMENTY
  // ===========================================================================
  const el = {
    // Header
    blenderIndicator: document.getElementById('blender-indicator'),
    blenderStatusText: document.getElementById('blender-status-text'),
    ragStatusText: document.getElementById('rag-status-text'),
    btnOpenRag: document.getElementById('btn-open-rag'),
    btnOpenSettings: document.getElementById('btn-open-settings'),

    // Sidebar
    btnNewChat: document.getElementById('btn-new-chat'),
    sessionSearch: document.getElementById('session-search-input'),
    sessionsContainer: document.getElementById('sessions-container'),

    // Chat
    activeSessionTitle: document.getElementById('active-session-title'),
    selectPreset: document.getElementById('select-preset'),
    toggleOnline: document.getElementById('toggle-online'),
    toggleRag: document.getElementById('toggle-rag'),
    toggleTts: document.getElementById('toggle-tts'),
    btnClearChat: document.getElementById('btn-clear-chat'),
    chatViewport: document.getElementById('chat-viewport'),
    welcomeHero: document.getElementById('welcome-hero'),
    messagesContainer: document.getElementById('messages-container'),

    // Prompt Bar
    promptInput: document.getElementById('prompt-input'),
    btnSend: document.getElementById('btn-send'),
    btnStop: document.getElementById('btn-stop'),
    fileInput: document.getElementById('file-input'),
    btnMic: document.getElementById('btn-mic'),
    attachedFileBanner: document.getElementById('attached-file-banner'),
    attachedFileName: document.getElementById('attached-file-name'),
    btnRemoveAttachment: document.getElementById('btn-remove-attachment'),
    liveStatusBadge: document.getElementById('live-status-badge'),
    liveStatusText: document.getElementById('live-status-text'),

    // 3D Inspector
    btnRefreshTelemetry: document.getElementById('btn-refresh-telemetry'),
    viewportSnapshotImg: document.getElementById('viewport-snapshot-img'),
    viewportBadge: document.getElementById('viewport-badge'),
    btnTakeSnapshot: document.getElementById('btn-take-snapshot'),
    
    // Metrics
    valTotalObjects: document.getElementById('val-total-objects'),
    valActiveMesh: document.getElementById('val-active-mesh'),
    valTotalFaces: document.getElementById('val-total-faces'),
    valTotalVerts: document.getElementById('val-total-verts'),
    valWatertight: document.getElementById('val-watertight'),
    valBones: document.getElementById('val-bones'),

    // Quick Actions
    btnQuickInspect: document.getElementById('btn-quick-inspect'),
    btnQuickAutorig: document.getElementById('btn-quick-autorig'),
    btnQuickMeshdoctor: document.getElementById('btn-quick-meshdoctor'),
    btnQuickStudio: document.getElementById('btn-quick-studio'),
    btnQuickShader: document.getElementById('btn-quick-shader'),

    // Console
    consoleOutput: document.getElementById('console-output'),
    btnClearConsole: document.getElementById('btn-clear-console'),

    // Modals
    modalRag: document.getElementById('modal-rag'),
    btnCloseRagModal: document.getElementById('btn-close-rag-modal'),
    ragDropzone: document.getElementById('rag-dropzone'),
    ragFileInput: document.getElementById('rag-file-modal-input'),
    modalDocsList: document.getElementById('modal-docs-list'),
    btnReindexMemory: document.getElementById('btn-reindex-memory'),

    modalSettings: document.getElementById('modal-settings'),
    btnCloseSettingsModal: document.getElementById('btn-close-settings-modal'),
    cfgTemp: document.getElementById('cfg-temp'),
    cfgTokens: document.getElementById('cfg-tokens'),
    cfgSysprompt: document.getElementById('cfg-sysprompt'),
    btnSaveSettings: document.getElementById('btn-save-settings'),

    // Lightbox
    imageLightbox: document.getElementById('image-lightbox'),
    lightboxImg: document.getElementById('lightbox-img'),
    btnCloseLightbox: document.getElementById('btn-close-lightbox'),
  };

  // ===========================================================================
  // POMOCNÉ FUNKCE: TELEMETRICKÝ LOG
  // ===========================================================================
  const MAX_CONSOLE_LINES = 200;
  function logConsole(message, type = 'info') {
    if (!el.consoleOutput) return;
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${message}`;
    el.consoleOutput.appendChild(line);

    // Omezení počtu položek v DOMu (FIFO) pro prevenci nekonečného růstu paměti
    while (el.consoleOutput.children.length > MAX_CONSOLE_LINES) {
      el.consoleOutput.removeChild(el.consoleOutput.firstElementChild || el.consoleOutput.firstChild);
    }

    el.consoleOutput.scrollTop = el.consoleOutput.scrollHeight;
  }

  // ===========================================================================
  // MARKDOWN RENDERER (LEHKÝ, BEZPEČNÝ, RYCHLÝ)
  // ===========================================================================
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderMarkdown(rawText) {
    if (!rawText) return '';

    // Extrakce bloků kódu
    const codeBlocks = [];
    let text = rawText.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      const cleanLang = lang.trim() || 'code';
      const cleanCode = escapeHtml(code.trim());
      codeBlocks.push(
        `<div class="code-block">` +
          `<div class="code-block-header">` +
            `<span class="code-block-lang">${cleanLang}</span>` +
            `<button class="copy-code-btn" onclick="navigator.clipboard.writeText(this.dataset.code); this.textContent='Zkopírováno!'; setTimeout(() => this.textContent='Kopírovat', 2000);" data-code="${escapeHtml(code.trim())}">Kopírovat</button>` +
          `</div>` +
          `<pre><code>${cleanCode}</code></pre>` +
        `</div>`
      );
      return `@@@CODEBLOCK_${idx}@@@`;
    });

    // Základní formátování
    text = escapeHtml(text);

    // Vizuální hlášky / tool alert bloky
    text = text.replace(/^&gt;\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/gim, (m, alertType, content) => {
      return `<div class="tool-result-box ${alertType.toLowerCase()}"><strong>[${alertType}]</strong> ${content}</div>`;
    });

    // Nadpisy
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Tučné & kurzíva
    text = text.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline kód
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Odrážky
    text = text.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    // Oprava vnořených ul
    text = text.replace(/<\/ul>\s*<ul>/g, '');

    // Blokové citace
    text = text.replace(/^&gt;\s+(.*)$/gim, '<blockquote>$1</blockquote>');
    text = text.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');

    // Odkazy (striktní validace schémat — povoleno pouze http:// a https://; blokování javascript:, data: atd. nahrazením za #)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, rawUrl) => {
      const trimmedUrl = rawUrl.trim();
      const isSafe = /^https?:\/\//i.test(trimmedUrl);
      const safeHref = isSafe ? escapeHtml(trimmedUrl) : '#';
      return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });

    // Detekce obrázku / náhledu viewportu
    text = text.replace(/(\/tmp\/[a-zA-Z0-9_\-]+\.png)/g, (match) => {
      return `<div class="chat-viewport-embed"><img src="/api/blender/viewport-image?t=${Date.now()}" alt="Viewport Screenshot" class="clickable-snapshot" onclick="window.openLightbox(this.src)" /><span class="embed-caption">📸 ${match}</span></div>`;
    });

    // Řádkové zlomy v odstavcích
    text = text.replace(/\n\n+/g, '</p><p>');
    text = `<p>${text}</p>`;
    text = text.replace(/<p><\/p>/g, '');
    text = text.replace(/<p>(<div.*?<\/div>)<\/p>/g, '$1');
    text = text.replace(/<p>(<ul>.*?<\/ul>)<\/p>/g, '$1');
    text = text.replace(/<p>(<blockquote>.*?<\/blockquote>)<\/p>/g, '$1');
    text = text.replace(/<p>(<h[1-3]>.*?<\/h[1-3]>)<\/p>/g, '$1');

    // Vrácení kódových bloků
    text = text.replace(/@@@CODEBLOCK_(\d+)@@@/g, (match, idx) => {
      return codeBlocks[Number(idx)] || '';
    });

    return text;
  }

  // Zpřístupnit pro inline handlery
  window.openLightbox = (src) => {
    if (el.imageLightbox && el.lightboxImg) {
      el.lightboxImg.src = src;
      el.imageLightbox.style.display = 'flex';
    }
  };

  // ===========================================================================
  // SPRÁVA RELACÍ (SESSIONS)
  // ===========================================================================
  async function loadSessions(targetSelectId = null) {
    try {
      const res = await fetch('/api/sessions');
      if (!res.ok) throw new Error('Chyba při načítání relací');
      const data = await res.json();
      state.sessions = data.sessions || [];
      renderSessionsList();

      if (state.sessions.length > 0) {
        const first = state.sessions[0];
        const idToSelect = targetSelectId || state.sessionId || (first ? (first.session_id || first.id) : null);
        await selectSession(idToSelect);
      } else {
        await createNewSession();
      }
    } catch (err) {
      logConsole(`Chyba načtení relací: ${err.message}`, 'error');
    }
  }

  function renderSessionsList(filterText = '') {
    if (!el.sessionsContainer) return;
    el.sessionsContainer.innerHTML = '';

    const query = filterText.toLowerCase().trim();
    const filtered = state.sessions.filter(s => {
      return !query || (s.title && s.title.toLowerCase().includes(query));
    });

    if (filtered.length === 0) {
      el.sessionsContainer.innerHTML = '<div style="padding: 12px 14px; font-size: 12px; color: var(--color-text-muted);">Žádné relace.</div>';
      return;
    }

    filtered.forEach(s => {
      const sid = s.session_id || s.id;
      const item = document.createElement('div');
      item.className = `session-item ${sid === state.sessionId ? 'active' : ''}`;
      item.dataset.id = sid;

      const dateStr = s.updated_at ? new Date(s.updated_at).toLocaleDateString() : '';

      item.innerHTML = `
        <div class="session-item-content">
          <div class="session-item-title">${escapeHtml(s.title || 'Nepojmenovaná relace')}</div>
          <div class="session-item-time">${dateStr}</div>
        </div>
        <div class="session-actions">
          <button class="session-action-btn delete-btn" title="Smazat relaci" data-action="delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      `;

      item.addEventListener('click', (e) => {
        if (state.isStreaming) {
          logConsole('Během probíhajícího generování nelze přepínat ani mazat relace.', 'warn');
          return;
        }
        if (e.target.closest('[data-action="delete"]')) {
          e.stopPropagation();
          deleteSession(sid);
          return;
        }
        selectSession(sid);
      });

      el.sessionsContainer.appendChild(item);
    });
  }

  async function createNewSession() {
    if (state.isStreaming) {
      logConsole('Nelze vytvořit novou relaci během probíhajícího generování.', 'warn');
      return;
    }
    try {
      const res = await fetch('/api/sessions?title=Nový%20chat', { method: 'POST' });
      if (!res.ok) throw new Error('Nepodařilo se vytvořit relaci');
      const newSess = await res.json();
      state.sessions.unshift(newSess);
      const sid = newSess.session_id || newSess.id;
      await selectSession(sid);
      renderSessionsList();
      logConsole(`Vytvořena nová relace: ${sid}`, 'info');
      el.promptInput.focus();
    } catch (err) {
      logConsole(`Chyba vytvoření relace: ${err.message}`, 'error');
    }
  }

  async function selectSession(sessionId) {
    if (!sessionId) return;

    if (state.isStreaming) {
      logConsole('Nelze přepínat konverzace během probíhajícího generování. Nejprve zastavte generování.', 'warn');
      return;
    }

    // Zrušit dřívější nedokončený dotaz na relaci
    if (state.selectSessionAbortController) {
      state.selectSessionAbortController.abort();
    }
    state.selectSessionAbortController = new AbortController();
    const currentSeq = ++state.selectSessionSeq;

    state.sessionId = sessionId;

    // Aktualizace aktivní třídy v sidebar
    document.querySelectorAll('.session-item').forEach(node => {
      node.classList.toggle('active', node.dataset.id === sessionId);
    });

    // Načíst zprávy
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, {
        signal: state.selectSessionAbortController.signal,
      });
      if (!res.ok) throw new Error('Relace nenalezena');
      const data = await res.json();

      // Ochrana proti Race Condition: ignorovat zpožděné odpovědi starších požadavků
      if (currentSeq !== state.selectSessionSeq || state.sessionId !== sessionId) {
        return;
      }
      
      const current = state.sessions.find(s => (s.session_id === sessionId || s.id === sessionId));
      if (el.activeSessionTitle) {
        el.activeSessionTitle.textContent = current ? (current.title || 'Nepojmenovaná relace') : 'Konverzace';
      }

      renderMessages(data.messages || []);
    } catch (err) {
      if (err.name === 'AbortError') {
        return;
      }
      logConsole(`Chyba načítání zpráv: ${err.message}`, 'error');
    }
  }

  async function deleteSession(sessionId) {
    if (state.isStreaming) {
      logConsole('Během probíhajícího generování nelze mazat relace.', 'warn');
      return;
    }
    if (!confirm('Opravdu chcete smazat tuto relaci?')) return;
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Chyba při mazání relace');
      state.sessions = state.sessions.filter(s => (s.session_id !== sessionId && s.id !== sessionId));
      if (state.sessionId === sessionId) {
        state.sessionId = null;
        if (state.sessions.length > 0) {
          const nextFirst = state.sessions[0];
          await selectSession(nextFirst.session_id || nextFirst.id);
        } else {
          await createNewSession();
        }
      }
      renderSessionsList();
      logConsole(`Relace ${sessionId} smazána.`, 'warn');
    } catch (err) {
      logConsole(`Chyba při mazání: ${err.message}`, 'error');
    }
  }

  async function renameSession(sessionId, newTitle) {
    const clean = newTitle.trim();
    if (!clean) return;
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: clean }),
      });
      if (!res.ok) throw new Error('Nepodařilo se přejmenovat');
      const target = state.sessions.find(s => (s.session_id === sessionId || s.id === sessionId));
      if (target) target.title = clean;
      renderSessionsList();
      logConsole(`Relace přejmenována na: ${clean}`, 'info');
    } catch (err) {
      logConsole(`Chyba přejmenování: ${err.message}`, 'error');
    }
  }

  async function clearCurrentSession() {
    if (!state.sessionId) return;
    if (!confirm('Opravdu chcete vymazat historii zpráv této relace?')) return;
    try {
      const res = await fetch(`/api/sessions/${state.sessionId}/messages`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Nepodařilo se vymazat zprávy');
      renderMessages([]);
      logConsole(`Historie relace ${state.sessionId} vymazána.`, 'warn');
    } catch (err) {
      logConsole(`Chyba: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // VYKRESLOVÁNÍ ZPRÁV V CHATU
  // ===========================================================================
  function renderMessages(messages) {
    if (!el.messagesContainer || !el.welcomeHero) return;
    el.messagesContainer.innerHTML = '';

    if (!messages || messages.length === 0) {
      el.welcomeHero.style.display = 'flex';
      return;
    }

    el.welcomeHero.style.display = 'none';

    messages.forEach(msg => {
      appendMessageCard(msg.role, msg.content, false);
    });

    scrollToBottom();
  }

  function appendMessageCard(role, initialContent = '', isLive = false) {
    if (el.welcomeHero) {
      el.welcomeHero.style.display = 'none';
    }

    const card = document.createElement('div');
    card.className = `message-card ${role === 'user' ? 'user-card' : 'assistant-card'}`;

    const isUser = role === 'user';
    const avatarLetter = isUser ? 'U' : 'A';
    const authorName = isUser ? 'Vy' : 'Polygon Beater Core';

    card.innerHTML = `
      <div class="message-card-header">
        <div class="message-avatar">${avatarLetter}</div>
        <span class="message-author">${authorName}</span>
        <span class="message-timestamp">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="message-tool-status-area" style="display: none;"></div>
      <div class="message-body">${isUser ? escapeHtml(initialContent) : renderMarkdown(initialContent)}</div>
    `;

    el.messagesContainer.appendChild(card);
    scrollToBottom();
    return card;
  }

  function scrollToBottom() {
    if (el.chatViewport) {
      el.chatViewport.scrollTop = el.chatViewport.scrollHeight;
    }
  }

  // ===========================================================================
  // CHAT STREAMING (SSE POST /api/chat)
  // ===========================================================================
  async function sendMessage() {
    if (state.isStreaming) return;

    const rawPrompt = el.promptInput.value.trim();
    if (!rawPrompt && !state.attachedFile) return;

    // Pokud je prázdný prompt, ale je přiložena příloha, doplníme výchozí text
    // aby backend (který vyžaduje neprázdné pole prompt) nevrátil chybu 400.
    const effectivePrompt = (rawPrompt || (state.attachedFile
      ? 'Zpracuj tento přiložený dokument.'
      : ''));

    // 1. Zpracování přílohy, pokud je přítomna
    if (state.attachedFile) {
      const uploaded = await uploadPendingAttachment();
      if (!uploaded) return;
    }

    const promptText = effectivePrompt;
    el.promptInput.value = '';
    el.promptInput.style.height = 'auto';

    // Zajistit platné ID aktivní relace
    if (!state.sessionId) {
      if (state.sessions && state.sessions.length > 0) {
        const first = state.sessions[0];
        state.sessionId = first.session_id || first.id;
      } else {
        try {
          const sRes = await fetch('/api/sessions?title=Nov%C3%BD%20chat', { method: 'POST' });
          if (sRes.ok) {
            const sData = await sRes.json();
            state.sessionId = sData.session_id || sData.id;
            state.sessions.unshift(sData);
            renderSessionsList();
          }
        } catch (e) {
          // fallback
        }
      }
    }

    // Vložení uživatelské zprávy
    appendMessageCard('user', promptText, false);

    // Příprava asistenta
    state.isStreaming = true;
    updateStreamingUi(true);

    const assistantCard = appendMessageCard('assistant', '', true);
    const bodyEl = assistantCard.querySelector('.message-body');
    const toolArea = assistantCard.querySelector('.message-tool-status-area');

    let fullText = '';
    state.abortController = new AbortController();

    try {
      const payload = {
        session_id: state.sessionId || '',
        sessionId: state.sessionId || '',
        prompt: promptText,
        message: promptText,
        analytical_preset: state.selectedPreset || '',
        methodology: state.selectedPreset || '',
        online_mode: Boolean(state.onlineMode),
        tools_enabled: Boolean(state.onlineMode),
        rag_enabled: Boolean(state.ragEnabled),
      };

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: state.abortController.signal,
      });

      if (!response.ok) {
        let errDetail = response.statusText;
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || JSON.stringify(errJson);
        } catch (e) {
          // ignore
        }
        throw new Error(`HTTP ${response.status}: ${errDetail}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // poslední neúplný chunk zůstává

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);

            if (data.type === 'session_id') {
              if (data.content && (!state.sessionId || state.sessionId !== data.content)) {
                state.sessionId = data.content;
              }
            } else if (data.type === 'token') {
              fullText += data.content;
              bodyEl.innerHTML = renderMarkdown(fullText);
              scrollToBottom();
            } else if (data.type === 'status') {
              if (toolArea) {
                toolArea.style.display = 'block';
                const pill = document.createElement('div');
                pill.className = 'tool-status-pill';
                pill.textContent = data.content;
                toolArea.appendChild(pill);
              }
              if (el.liveStatusText) {
                el.liveStatusText.textContent = data.content;
              }
              logConsole(data.content, 'info');
              scrollToBottom();
            } else if (data.type === 'methodology') {
              logConsole(`Detekována metodika: ${data.content}`, 'info');
            } else if (data.type === 'done') {
              fullText = data.content || fullText;
              bodyEl.innerHTML = renderMarkdown(fullText);
              scrollToBottom();
            } else if (data.type === 'error') {
              bodyEl.innerHTML += `<div class="error-badge">⚠️ ${escapeHtml(data.content)}</div>`;
              logConsole(`Chyba: ${data.content}`, 'error');
            }
          } catch (e) {
            // Parsovací reziduum
          }
        }
      }

      // Aktualizace názvu relace, pokud jde o první zprávu
      const current = state.sessions.find(s => (s.session_id === state.sessionId || s.id === state.sessionId));
      if (current && (current.title === 'Nový chat' || current.title === 'Nepojmenovaná relace')) {
        const autoTitle = promptText.slice(0, 32).trim() + (promptText.length > 32 ? '…' : '');
        renameSession(state.sessionId, autoTitle);
      }

      // Volitelná hlasová syntéza (TTS)
      if (state.ttsEnabled && fullText) {
        speakText(fullText);
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        logConsole('Generování bylo přerušeno uživatelem.', 'warn');
        bodyEl.innerHTML += `<div class="tool-status-pill abort-pill">⏹ Generování zastaveno</div>`;
      } else {
        logConsole(`Chyba komunikace s backendem: ${err.message}`, 'error');
        bodyEl.innerHTML += `<div class="error-badge">Chyba spojení: ${escapeHtml(err.message)}</div>`;
      }
    } finally {
      state.isStreaming = false;
      state.abortController = null;
      updateStreamingUi(false);
      scrollToBottom();
    }
  }

  async function stopGeneration() {
    if (!state.isStreaming) return;
    try {
      if (state.abortController) {
        state.abortController.abort();
      }
      const sid = state.sessionId || '';
      await fetch('/api/chat/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, sessionId: sid }),
      });
    } catch (e) {
      // Ignorovat
    }
  }

  function updateStreamingUi(isStreaming) {
    if (el.btnSend && el.btnStop && el.liveStatusBadge) {
      el.btnSend.style.display = isStreaming ? 'none' : 'flex';
      el.btnStop.style.display = isStreaming ? 'flex' : 'none';
      el.liveStatusBadge.style.display = isStreaming ? 'inline-flex' : 'none';
      if (isStreaming) {
        el.liveStatusText.textContent = 'Přemýšlím…';
      }
    }
    if (el.sessionsContainer) {
      el.sessionsContainer.classList.toggle('disabled-streaming', isStreaming);
    }
    if (el.btnNewChat) {
      el.btnNewChat.disabled = isStreaming;
      el.btnNewChat.style.opacity = isStreaming ? '0.5' : '1';
      el.btnNewChat.style.pointerEvents = isStreaming ? 'none' : 'auto';
    }
  }

  // ===========================================================================
  // RAG PŘÍLOHY & UPLOAD
  // ===========================================================================
  function setAttachedFile(file) {
    state.attachedFile = file;
    if (file) {
      el.attachedFileName.textContent = `${file.name} (${Math.round(file.size / 1024)} kB)`;
      el.attachedFileBanner.style.display = 'inline-flex';
    } else {
      el.attachedFileBanner.style.display = 'none';
      if (el.fileInput) el.fileInput.value = '';
    }
  }

  async function uploadPendingAttachment() {
    if (!state.attachedFile) return;
    const formData = new FormData();
    formData.append('file', state.attachedFile);

    try {
      logConsole(`Nahrávám dokument do RAG: ${state.attachedFile.name}...`, 'info');
      const res = await fetch('/api/rag/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const data = await res.json();
          detail = data.detail || detail;
        } catch (e) {
          // Keep the HTTP status text when the error response is not JSON.
        }
        throw new Error(`HTTP ${res.status}: ${detail}`);
      }
      const data = await res.json();
      if (!Number.isInteger(data.chunks_indexed) || data.chunks_indexed < 1) {
        throw new Error('V souboru nebyl nalezen žádný indexovatelný text.');
      }
      logConsole(`Indexace dokončena: ${data.filename} (${data.chunks_indexed} chunků)`, 'info');
      setAttachedFile(null);
      await refreshSystemStatus();
      return true;
    } catch (err) {
      logConsole(`Chyba indexace přílohy: ${err.message}`, 'error');
      return false;
    }
  }

  // ===========================================================================
  // 3D BLENDER BRIDGE & TELEMETRIE
  // ===========================================================================
  async function refreshBlenderStatus() {
    try {
      const res = await fetch('/api/blender/status');
      if (!res.ok) return;
      const data = await res.json();
      state.blenderConnected = Boolean(data.connected);

      if (el.blenderIndicator && el.blenderStatusText) {
        el.blenderIndicator.className = `status-indicator ${data.connected ? 'online' : 'offline'}`;
        el.blenderStatusText.textContent = `Blender: ${data.connected ? 'Připojen' : 'Offline'}`;
      }

      if (el.viewportBadge) {
        el.viewportBadge.className = `card-badge ${data.connected ? 'badge-online' : 'badge-offline'}`;
        el.viewportBadge.textContent = data.connected ? 'Aktivní' : 'Offline';
      }
    } catch (e) {
      if (el.blenderIndicator && el.blenderStatusText) {
        el.blenderIndicator.className = 'status-indicator offline';
        el.blenderStatusText.textContent = 'Blender: Offline';
      }
    }
  }

  async function takeBlenderInspection() {
    logConsole('Vyžaduji inspekci viewportu a sběr telemetrie...', 'info');
    try {
      const res = await fetch('/api/blender/inspect', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      if (data.status === 'error') {
        throw new Error(data.detail || data.message || data.error || 'Inspekce Blenderu selhala.');
      }
      
      // Aktualizovat obrázek s cache bustem
      if (el.viewportSnapshotImg) {
        el.viewportSnapshotImg.src = `/api/blender/viewport-image?t=${Date.now()}`;
      }

      // Aktualizovat metriky
      updateTelemetryMetrics(data);
      const metrics = data.scene_metrics || data;
      const activeName = metrics.active_object?.name || metrics.active_object || 'žádný';
      logConsole(`Inspekce hotova: ${metrics.total_objects ?? metrics.objects_count ?? 0} objektů, aktivní: ${activeName}`, 'info');
    } catch (err) {
      logConsole(`Chyba inspekce Blenderu: ${err.message}`, 'error');
    }
  }

  function updateTelemetryMetrics(data) {
    if (!data) return;
    const metrics = data.scene_metrics || data;
    const activeObject = metrics.active_object;
    if (el.valTotalObjects) el.valTotalObjects.textContent = metrics.total_objects ?? metrics.objects_count ?? '-';
    if (el.valActiveMesh) el.valActiveMesh.textContent = activeObject?.name || activeObject || 'Žádný';
    const faces = activeObject?.polygons ?? metrics.faces_count;
    const vertices = activeObject?.vertices ?? metrics.vertices_count;
    if (el.valTotalFaces) el.valTotalFaces.textContent = faces != null ? Number(faces).toLocaleString() : '-';
    if (el.valTotalVerts) el.valTotalVerts.textContent = vertices != null ? Number(vertices).toLocaleString() : '-';
    
    if (el.valWatertight) {
      if (data.watertight !== undefined) {
        el.valWatertight.textContent = data.watertight ? 'ANO' : 'NE';
        el.valWatertight.className = `metric-value ${data.watertight ? 'metric-ok' : 'metric-warn'}`;
      } else {
        el.valWatertight.textContent = '-';
      }
    }

    if (el.valBones) {
      el.valBones.textContent = data.bones_count !== undefined ? data.bones_count : (data.bones || '-');
    }
  }

  async function executeQuick3DAction(endpoint, actionName, bodyObj = null) {
    logConsole(`Spouštím 3D operaci: ${actionName}...`, 'info');
    try {
      const options = { method: 'POST' };
      if (bodyObj) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(bodyObj);
      }
      const res = await fetch(endpoint, options);
      const data = await res.json();
      logConsole(`Výsledek [${actionName}]: ${JSON.stringify(data)}`, 'info');

      // Obnovit náhled a metriky po akci
      setTimeout(takeBlenderInspection, 500);
    } catch (err) {
      logConsole(`Chyba při operaci ${actionName}: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // RAG & KNOWLEDGE BASE MODAL
  // ===========================================================================
  async function openRagModal() {
    if (!el.modalRag) return;
    el.modalRag.style.display = 'flex';
    await loadRagDocuments();
  }

  function closeRagModal() {
    if (el.modalRag) el.modalRag.style.display = 'none';
  }

  async function loadRagDocuments() {
    if (!el.modalDocsList) return;
    try {
      const res = await fetch('/api/rag/documents');
      const data = await res.json();
      const docs = data.documents || [];
      
      if (docs.length === 0) {
        el.modalDocsList.innerHTML = '<div style="color: var(--color-text-muted); font-size: 13px;">Zatím nejsou indexovány žádné dokumenty.</div>';
        return;
      }

      el.modalDocsList.innerHTML = '';
      docs.forEach(doc => {
        const item = document.createElement('div');
        item.className = 'indexed-doc-item';

        const title = document.createElement('div');
        title.className = 'doc-item-title';
        title.textContent = `📄 ${doc}`;

        const removeButton = document.createElement('button');
        removeButton.className = 'doc-delete-btn';
        removeButton.textContent = 'Odstranit';
        removeButton.addEventListener('click', () => window.deleteRagDoc(doc));

        item.append(title, removeButton);
        el.modalDocsList.appendChild(item);
      });

    } catch (err) {
      logConsole(`Chyba načtení RAG dokumentů: ${err.message}`, 'error');
    }
  }

  window.deleteRagDoc = async (docName) => {
    if (!confirm(`Opravdu chcete odebrat "${docName}" z indexu RAG?`)) return;
    try {
      const res = await fetch(`/api/rag/documents/${encodeURIComponent(docName)}`, { method: 'DELETE' });
      if (res.ok) {
        logConsole(`Dokument "${docName}" odstraněn.`, 'info');
        await loadRagDocuments();
        await refreshSystemStatus();
      }
    } catch (e) {
      logConsole(`Chyba mazání: ${e.message}`, 'error');
    }
  };

  async function reindexAllMemory() {
    logConsole('Spouštím reindexaci sémantické paměti a relací...', 'info');
    try {
      const res = await fetch('/api/rag/memory/reindex', { method: 'POST' });
      const data = await res.json();
      logConsole(`Reindexace hotova: ${JSON.stringify(data.result || data)}`, 'info');
      await refreshSystemStatus();
    } catch (e) {
      logConsole(`Chyba reindexace: ${e.message}`, 'error');
    }
  }

  // ===========================================================================
  // NASTAVENÍ MODAL
  // ===========================================================================
  async function openSettingsModal() {
    if (!el.modalSettings) return;
    el.modalSettings.style.display = 'flex';
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      const cfg = data.config || {};
      const llama = cfg.llama || {};

      if (el.cfgTemp) el.cfgTemp.value = llama.temperature ?? 0.7;
      if (el.cfgTokens) el.cfgTokens.value = llama.max_tokens ?? 750;
      if (el.cfgSysprompt) el.cfgSysprompt.value = llama.system_prompt ?? data.default_system_prompt ?? '';
    } catch (e) {
      logConsole(`Chyba načítání konfigurace: ${e.message}`, 'error');
    }
  }

  function closeSettingsModal() {
    if (el.modalSettings) el.modalSettings.style.display = 'none';
  }

  async function saveSettings() {
    try {
      const payload = {
        temperature: parseFloat(el.cfgTemp.value) || 0.7,
        max_tokens: parseInt(el.cfgTokens.value, 10) || 750,
        system_prompt: el.cfgSysprompt.value,
      };

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error('Nepodařilo se uložit nastavení');
      logConsole('Konfigurace uložena.', 'info');
      closeSettingsModal();
    } catch (err) {
      logConsole(`Chyba ukládání konfigurace: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // SYSTÉMOVÝ STAV (STATUS POLL)
  // ===========================================================================
  async function refreshSystemStatus() {
    try {
      const res = await fetch('/api/status');
      if (!res.ok) return;
      const data = await res.json();

      // RAG status
      if (el.ragStatusText) {
        const docCount = data.rag?.total_documents ?? 0;
        const chunkCount = data.rag?.total_chunks ?? 0;
        el.ragStatusText.textContent = `RAG: ${docCount} souborů (${chunkCount} úseků)`;
      }

      // Presety
      if (data.analytical_presets && el.selectPreset) {
        const currentVal = el.selectPreset.value;
        const existingValues = Array.from(el.selectPreset.options).map(o => o.value);
        data.analytical_presets.forEach(presetName => {
          if (!existingValues.includes(presetName)) {
            const opt = document.createElement('option');
            opt.value = presetName;
            opt.textContent = presetName;
            el.selectPreset.appendChild(opt);
          }
        });
        if (currentVal) el.selectPreset.value = currentVal;
      }
    } catch (e) {
      // Ignorovat
    }
  }

  // ===========================================================================
  // HLASOVÉ NAHRÁVÁNÍ (MIC / SPEECH-TO-TEXT) & TTS
  // ===========================================================================
  async function toggleMicrophoneRecording() {
    if (state.isStreaming) {
      logConsole('Během probíhajícího generování nelze spustit přepis hlasu.', 'warn');
      return;
    }

    if (state.transcriptionAbortController) {
      state.transcriptionAbortController.abort();
      logConsole('Přepis hlasové nahrávky byl zrušen.', 'warn');
      return;
    }

    if (state.isRecording) {
      // Zastavit nahrávání
      if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
      }
      state.isRecording = false;
      el.btnMic.classList.remove('recording');
      logConsole('Nahrávání zvuku zastaveno.', 'info');
    } else {
      // Spustit nahrávání
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.audioChunks = [];
        const supportedMimeType = [
          'audio/webm;codecs=opus',
          'audio/ogg;codecs=opus',
          'audio/mp4',
        ].find(type => MediaRecorder.isTypeSupported(type));
        state.mediaRecorder = new MediaRecorder(
          stream,
          supportedMimeType ? { mimeType: supportedMimeType } : undefined,
        );

        state.mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            state.audioChunks.push(event.data);
          }
        };

        state.mediaRecorder.onstop = async () => {
          stream.getTracks().forEach(track => track.stop());
          const audioBlob = new Blob(state.audioChunks, {
            type: state.mediaRecorder.mimeType || 'audio/webm',
          });
          state.audioChunks = [];
          logConsole(`Zvuk zaznamenán (${Math.round(audioBlob.size / 1024)} kB). Připravuji přepis...`, 'info');
          await transcribeRecordedAudio(audioBlob);
        };

        state.mediaRecorder.onerror = () => {
          stream.getTracks().forEach(track => track.stop());
          state.audioChunks = [];
          state.isRecording = false;
          el.btnMic.classList.remove('recording');
          logConsole('Nahrávání mikrofonu selhalo.', 'error');
        };

        state.mediaRecorder.start();
        state.isRecording = true;
        el.btnMic.classList.add('recording');
        logConsole('Hlasový odposlech aktivní (mluvte do mikrofonu)...', 'info');
      } catch (err) {
        state.audioChunks = [];
        logConsole(`Přístup k mikrofonu odmítnut: ${err.message}`, 'warn');
      }
    }
  }

  async function transcribeRecordedAudio(audioBlob) {
    if (!audioBlob.size) {
      logConsole('Nahrávka neobsahuje žádná zvuková data.', 'warn');
      return;
    }

    const extensionByType = {
      'audio/webm': 'webm',
      'audio/ogg': 'ogg',
      'audio/mp4': 'mp4',
      'audio/wav': 'wav',
    };
    const mimeType = audioBlob.type.split(';', 1)[0].toLowerCase();
    const extension = extensionByType[mimeType];
    if (!extension) {
      logConsole(`Nepodporovaný formát nahrávky: ${audioBlob.type || 'neznámý'}`, 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', audioBlob, `voice.${extension}`);
    const controller = new AbortController();
    state.transcriptionAbortController = controller;
    el.btnMic.classList.add('recording');
    try {
      const response = await fetch('/api/stt/transcribe', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      if (!response.ok) {
        let detail = response.statusText;
        try {
          const data = await response.json();
          detail = data.detail || detail;
        } catch (e) {
          // Keep the HTTP status text when the error response is not JSON.
        }
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      const data = await response.json();
      const transcript = typeof data.text === 'string' ? data.text.trim() : '';
      if (!transcript) {
        logConsole('V nahrávce nebyla rozpoznána žádná řeč.', 'warn');
        return;
      }
      logConsole(`Hlasový přepis: "${transcript}"`, 'info');
      el.promptInput.value = transcript;
      await sendMessage();
    } catch (err) {
      if (err.name === 'AbortError') {
        logConsole('Přepis hlasové nahrávky byl zrušen.', 'warn');
      } else {
        logConsole(`Chyba lokálního přepisu: ${err.message}`, 'error');
      }
    } finally {
      if (state.transcriptionAbortController === controller) {
        state.transcriptionAbortController = null;
      }
      el.btnMic.classList.remove('recording');
    }
  }

  function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const clean = text.replace(/```[\s\S]*?```/g, '').replace(/[#*`_>]/g, '').trim();
    if (!clean) return;
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = 'cs-CZ';
    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  }

  // ===========================================================================
  // EVENT LISTENERS & INICIALIZACE
  // ===========================================================================
  function setupEventListeners() {
    // Send / Stop
    if (el.btnSend) el.btnSend.addEventListener('click', sendMessage);
    if (el.btnStop) el.btnStop.addEventListener('click', stopGeneration);

    // Prompt input auto-expand & enter send
    if (el.promptInput) {
      el.promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });

      el.promptInput.addEventListener('input', () => {
        el.promptInput.style.height = 'auto';
        el.promptInput.style.height = Math.min(el.promptInput.scrollHeight, 180) + 'px';
      });
    }

    // Suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.dataset.prompt;
        if (text && el.promptInput) {
          el.promptInput.value = text;
          sendMessage();
        }
      });
    });

    // Přejmenování relace kliknutím
    if (el.activeSessionTitle) {
      el.activeSessionTitle.addEventListener('blur', () => {
        if (state.sessionId) {
          renameSession(state.sessionId, el.activeSessionTitle.textContent);
        }
      });
      el.activeSessionTitle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          el.activeSessionTitle.blur();
        }
      });
    }

    // Tlačítko nové relace
    if (el.btnNewChat) el.btnNewChat.addEventListener('click', createNewSession);

    // Vyhledávání v relacích
    if (el.sessionSearch) {
      el.sessionSearch.addEventListener('input', (e) => {
        renderSessionsList(e.target.value);
      });
    }

    // Vymazat chat
    if (el.btnClearChat) el.btnClearChat.addEventListener('click', clearCurrentSession);

    // Výběr metodiky
    if (el.selectPreset) {
      el.selectPreset.addEventListener('change', (e) => {
        state.selectedPreset = e.target.value;
        logConsole(`Aktivována metodika: ${state.selectedPreset}`, 'info');
      });
    }

    // Toggles
    if (el.toggleOnline) {
      el.toggleOnline.addEventListener('click', () => {
        state.onlineMode = !state.onlineMode;
        el.toggleOnline.classList.toggle('active', state.onlineMode);
        logConsole(`Web Tools: ${state.onlineMode ? 'ZAPNUTO' : 'VYPNUTO'}`, 'info');
      });
    }

    if (el.toggleRag) {
      el.toggleRag.addEventListener('click', () => {
        state.ragEnabled = !state.ragEnabled;
        el.toggleRag.classList.toggle('active', state.ragEnabled);
        logConsole(`RAG paměť: ${state.ragEnabled ? 'ZAPNUTO' : 'VYPNUTO'}`, 'info');
      });
    }

    if (el.toggleTts) {
      el.toggleTts.addEventListener('click', () => {
        state.ttsEnabled = !state.ttsEnabled;
        el.toggleTts.classList.toggle('active', state.ttsEnabled);
        logConsole(`TTS hlasová syntéza: ${state.ttsEnabled ? 'ZAPNUTO' : 'VYPNUTO'}`, 'info');
      });
    }

    // Přílohy souborů
    if (el.fileInput) {
      el.fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          setAttachedFile(e.target.files[0]);
        }
      });
    }

    if (el.btnRemoveAttachment) {
      el.btnRemoveAttachment.addEventListener('click', () => setAttachedFile(null));
    }

    // Mikrofon
    if (el.btnMic) el.btnMic.addEventListener('click', toggleMicrophoneRecording);

    // 3D Blender tlačítka
    if (el.btnTakeSnapshot) el.btnTakeSnapshot.addEventListener('click', takeBlenderInspection);
    if (el.btnRefreshTelemetry) el.btnRefreshTelemetry.addEventListener('click', () => {
      refreshBlenderStatus();
      takeBlenderInspection();
    });

    if (el.btnQuickInspect) el.btnQuickInspect.addEventListener('click', takeBlenderInspection);
    if (el.btnQuickAutorig) el.btnQuickAutorig.addEventListener('click', () => executeQuick3DAction('/api/blender/auto-rig', 'Auto-Rig & Skinning'));
    if (el.btnQuickMeshdoctor) el.btnQuickMeshdoctor.addEventListener('click', () => executeQuick3DAction('/api/blender/mesh-doctor', 'Mesh Doctor Audit'));
    if (el.btnQuickStudio) el.btnQuickStudio.addEventListener('click', () => executeQuick3DAction('/api/blender/product-studio', 'Produktové Studio'));
    if (el.btnQuickShader) el.btnQuickShader.addEventListener('click', () => executeQuick3DAction('/api/blender/procedural-shader', 'Kartáčovaný kov Shader'));

    if (el.btnClearConsole) {
      el.btnClearConsole.addEventListener('click', () => {
        if (el.consoleOutput) el.consoleOutput.innerHTML = '';
      });
    }

    // Viewport image zoom na kliknutí
    if (el.viewportSnapshotImg) {
      el.viewportSnapshotImg.addEventListener('click', () => {
        window.openLightbox(el.viewportSnapshotImg.src);
      });
    }

    // Modaly
    if (el.btnOpenRag) el.btnOpenRag.addEventListener('click', openRagModal);
    if (el.btnCloseRagModal) el.btnCloseRagModal.addEventListener('click', closeRagModal);
    if (el.btnOpenSettings) el.btnOpenSettings.addEventListener('click', openSettingsModal);
    if (el.btnCloseSettingsModal) el.btnCloseSettingsModal.addEventListener('click', closeSettingsModal);
    if (el.btnSaveSettings) el.btnSaveSettings.addEventListener('click', saveSettings);
    if (el.btnReindexMemory) el.btnReindexMemory.addEventListener('click', reindexAllMemory);

    // Zavření modalů klikem mimo okno
    window.addEventListener('click', (e) => {
      if (e.target === el.modalRag) closeRagModal();
      if (e.target === el.modalSettings) closeSettingsModal();
      if (e.target === el.imageLightbox) el.imageLightbox.style.display = 'none';
    });

    if (el.btnCloseLightbox) {
      el.btnCloseLightbox.addEventListener('click', () => {
        el.imageLightbox.style.display = 'none';
      });
    }

    // Drag & drop pro RAG modal
    if (el.ragDropzone && el.ragFileInput) {
      el.ragDropzone.addEventListener('click', () => el.ragFileInput.click());
      el.ragDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        el.ragDropzone.classList.add('dragover');
      });
      el.ragDropzone.addEventListener('dragleave', () => {
        el.ragDropzone.classList.remove('dragover');
      });
      el.ragDropzone.addEventListener('drop', async (e) => {
        e.preventDefault();
        el.ragDropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          const file = e.dataTransfer.files[0];
          const formData = new FormData();
          formData.append('file', file);
          logConsole(`Nahrávám "${file.name}" přes drag-and-drop...`, 'info');
          const res = await fetch('/api/rag/upload', { method: 'POST', body: formData });
          if (res.ok) {
            await loadRagDocuments();
            await refreshSystemStatus();
          }
        }
      });
      el.ragFileInput.addEventListener('change', async (e) => {
        if (e.target.files && e.target.files[0]) {
          const file = e.target.files[0];
          const formData = new FormData();
          formData.append('file', file);
          logConsole(`Nahrávám "${file.name}"...`, 'info');
          const res = await fetch('/api/rag/upload', { method: 'POST', body: formData });
          if (res.ok) {
            await loadRagDocuments();
            await refreshSystemStatus();
          }
        }
      });
    }

    // Globální klávesové zkratky
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        createNewSession();
      }
      if (e.key === 'Escape') {
        closeRagModal();
        closeSettingsModal();
        if (el.imageLightbox) el.imageLightbox.style.display = 'none';
      }
    });
  }

  // ===========================================================================
  // START APLIKACE
  // ===========================================================================
  async function init() {
    logConsole('Inicializuji Polygon Beater Web UI klienta...', 'info');
    setupEventListeners();
    await loadSessions();
    await refreshSystemStatus();
    await refreshBlenderStatus();

    // Pravidelný polling Blenderu každých 8 sekund
    state.blenderPollInterval = setInterval(refreshBlenderStatus, 8000);
    logConsole('Polygon Beater klient plně připraven k práci.', 'info');
  }

  // Spuštění po načtení DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
