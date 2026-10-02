/**
 * POLYGON BEATER — AI Assistant Voice CS
 * Frontend Client Controller (script.js)
 * 100% Vanilla JavaScript, no external dependencies, optimized for local offline operation.
 */

(() => {
  'use strict';

  // ===========================================================================
  // CLIENT STATE
  // ===========================================================================
  const state = {
    language: 'en',
    leftSidebarWidth: '280px',
    rightSidebarWidth: '340px',

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
    selectedPreset: 'standard',
    
    // Blender polling
    blenderConnected: false,
    blenderPollInterval: null,
  };

  // ===========================================================================
  // DOM ELEMENTS
  // ===========================================================================
  const el = {
    // Header
    blenderIndicator: document.getElementById('blender-indicator'),
    blenderStatusText: document.getElementById('blender-status-text'),
    ragStatusText: document.getElementById('rag-status-text'),
    btnOpenRag: document.getElementById('btn-open-rag'),
    btnOpenSettings: document.getElementById('btn-open-settings'),

    // Sidebar & Resizers
    leftSidebar: document.getElementById('left-sidebar'),
    rightInspector: document.getElementById('right-inspector'),
    resizerLeft: document.getElementById('resizer-left'),
    resizerRight: document.getElementById('resizer-right'),
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
    cfgLanguage: document.getElementById('cfg-language'),
    cfgTemp: document.getElementById('cfg-temp'),
    cfgTokens: document.getElementById('cfg-tokens'),
    cfgSysprompt: document.getElementById('cfg-sysprompt'),
    btnResetDefaults: document.getElementById('btn-reset-defaults'),
    btnSaveSettings: document.getElementById('btn-save-settings'),

    // Lightbox
    imageLightbox: document.getElementById('image-lightbox'),
    lightboxImg: document.getElementById('lightbox-img'),
    btnCloseLightbox: document.getElementById('btn-close-lightbox'),
  };

  // ===========================================================================
  // LOCALIZATION & I18N DICTIONARY (EN/CS)
  // ===========================================================================
  const I18N = {
    en: {
      status_llm: 'Qwen2.5-7B GGUF',
      status_blender_checking: 'Blender: Checking',
      status_blender_connected: 'Blender: Connected',
      status_blender_offline: 'Blender: Offline',
      status_rag: 'RAG: 100% Offline',
      btn_knowledge: 'Knowledge',
      btn_knowledge_title: 'Manage RAG documents and memory',
      btn_settings: 'Settings',
      btn_settings_title: 'Settings & Configuration',

      btn_new_chat: 'New conversation',
      search_sessions_placeholder: 'Search sessions...',
      section_history: 'CONVERSATION HISTORY',
      engine_name: 'Polygon Beater Core',
      engine_sub: '100% Local AI • Private',
      resizer_title_left: 'Drag to resize left sidebar',
      no_sessions: 'No sessions.',
      unnamed_session: 'Untitled conversation',
      delete_session_title: 'Delete session',

      chat_loading: 'Loading...',
      click_to_rename: 'Click to rename session',
      chat_tools_count: '22 Tools Active',
      select_preset_label: 'Methodology',
      select_preset_title: 'Select expert analytical framework',
      preset_standard: '🧠 Standard Assistant (Off)',
      preset_auto: '⚡ Auto-Select Methodology',
      preset_auteur: '🎬 Auteur & Visual Style',
      preset_first_principles: '📐 First Principles (3D CAD)',
      preset_red_team: '🛡️ Red Team & Counter-Analysis',
      preset_deep_analysis: '📊 In-Depth Analysis v3.1',
      preset_taleb: '📊 In-Depth Analysis v3.1',
      preset_assumption_audit: '🔍 Assumption Audit (Standard)',
      preset_assumption_audit_crisis: '🚨 Assumption Audit (Crisis)',
      preset_meta_analysis: '📑 Meta-Analysis (Full Template)',
      card_v_resizer_title: 'Drag to resize panel height',
      toggle_web_tools: 'Web Tools',
      toggle_web_tools_title: 'Enable web search and external tools',
      toggle_rag: 'RAG',
      toggle_rag_title: 'Semantic retrieval from RAG knowledge base',
      toggle_tts: 'TTS',
      toggle_tts_title: 'Voice synthesizer (TTS reading)',
      btn_clear_chat_title: 'Clear current session history',

      hero_title: 'AI Assistant Voice CS',
      hero_subtitle: 'Local Voice Companion & 3D Technical Director',
      chip_inspect_title: 'Inspect scene and viewport in Blender',
      chip_autorig_title: 'Apply Auto-Rig & Skinning (ARMATURE_AUTO)',
      chip_meshdoctor_title: 'Mesh Doctor topology audit (3D printing)',
      chip_studio_title: 'Create product studio with lighting',

      remove_attachment_title: 'Remove attachment',
      thinking_status: 'Thinking…',
      prompt_placeholder: 'Type a query or Blender command... (Enter to send, Shift+Enter for newline)',
      attach_file_title: 'Attach document for RAG (PDF, TXT, DOCX)',
      mic_btn_title: 'Voice recording (Whisper STT)',
      prompt_shortcut_hint: 'Enter to send • Shift+Enter for new line',
      send_btn_title: 'Send message',
      stop_btn_title: 'Stop generation',
      default_doc_prompt: 'Process this attached document.',

      resizer_title_right: 'Drag to resize right sidebar',
      inspector_title: '3D VIEWPORT & TELEMETRY',
      btn_refresh_telemetry_title: 'Refresh snapshot and metrics',
      card_viewport_title: 'LIVE VIEWPORT PREVIEW',
      viewport_active: 'Active',
      viewport_offline: 'Offline',
      btn_snapshot: 'Take screenshot',
      card_metrics_title: '3D SCENE METRICS',
      metric_total_objects: 'Total Objects',
      metric_active_mesh: 'Active MESH',
      metric_total_faces: 'Polygons Count',
      metric_total_verts: 'Vertices Count',
      metric_watertight: 'Watertight',
      metric_bones: 'Armature Bones',
      metric_yes: 'YES',
      metric_no: 'NO',
      metric_none: 'None',

      card_quick_actions: 'QUICK 3D COMMANDS (BLENDER)',
      qa_inspect_title: 'Viewport Inspection',
      qa_inspect_sub: 'Snapshot & telemetry collection',
      qa_autorig_title: 'Auto-Rig & Skinning',
      qa_autorig_sub: 'Armature + ARMATURE_AUTO',
      qa_meshdoctor_title: 'Mesh Doctor Audit',
      qa_meshdoctor_sub: 'Check manifold mesh for 3D printing',
      qa_studio_title: 'Product Studio',
      qa_studio_sub: '3-point AREA lighting + backdrop',
      qa_shader_title: 'Brushed Metal (Shader)',
      qa_shader_sub: 'Procedural Principled BSDF tree',
      card_console_title: 'TELEMETRIC CONSOLE',
      btn_clear_console: 'Clear',

      modal_rag_title: 'Knowledge Base & RAG Documents',
      modal_rag_desc: 'Documents indexed in local semantic memory (FAISS). The model retrieves facts without cloud upload.',
      rag_dropzone_text: 'Click or drag documents here (PDF, TXT, DOCX, MD)',
      modal_indexed_docs_header: 'Indexed Documents:',
      no_indexed_docs: 'No documents indexed yet.',
      btn_delete_doc: 'Delete',
      btn_reindex_memory: 'Reindex Semantic Memory',

      modal_settings_title: 'AI Assistant Configuration',
      cfg_language: 'Interface Language:',
      cfg_temp: 'Creativity / Temperature:',
      cfg_tokens: 'Maximum Response Tokens:',
      cfg_sysprompt: 'System Prompt:',
      btn_reset_defaults: 'Reset to Defaults',
      btn_save_settings: 'Save Settings',

      confirm_reset_defaults: 'Reset all interface preferences to factory defaults (English, default sidebar widths, clean layout)?',
      confirm_clear_session: 'Are you sure you want to clear message history for this session?',
      confirm_delete_rag_doc: 'Are you sure you want to remove "{name}" from RAG index?',
      new_chat_title: 'New chat',
      copy_code: 'Copy',
      copied_code: 'Copied!',
      you: 'You',
      stopped_pill: 'Generation stopped',
      rag_status_files: 'RAG: {docs} files ({chunks} chunks)',
      blender_connected: 'Connected',
      blender_offline: 'Offline',
      config_saved: 'Configuration saved successfully.',
      error_save_config: 'Failed to save configuration',
      error_saving_config: 'Error saving configuration',
      log_session_deleted: 'Session {id} deleted.',
    },
    cs: {
      status_llm: 'Qwen2.5-7B GGUF',
      status_blender_checking: 'Blender: Ověřuji',
      status_blender_connected: 'Blender: Připojen',
      status_blender_offline: 'Blender: Offline',
      status_rag: 'RAG: 100% Offline',
      btn_knowledge: 'Znalosti',
      btn_knowledge_title: 'Správa RAG dokumentů a paměti',
      btn_settings: 'Nastavení',
      btn_settings_title: 'Nastavení a konfigurace',

      btn_new_chat: 'Nová konverzace',
      search_sessions_placeholder: 'Hledat v relacích...',
      section_history: 'HISTORIE KONVERZACÍ',
      engine_name: 'Polygon Beater Core',
      engine_sub: '100% Lokální AI • Soukromé',
      resizer_title_left: 'Tažením změnit šířku levého panelu',
      no_sessions: 'Žádné relace.',
      unnamed_session: 'Nepojmenovaná relace',
      delete_session_title: 'Smazat relaci',

      chat_loading: 'Načítám...',
      click_to_rename: 'Klikněte pro přejmenování relace',
      chat_tools_count: '22 Nástrojů aktivních',
      select_preset_label: 'Metodika',
      select_preset_title: 'Vyberte expertní analytický rámec',
      preset_standard: '🧠 Standardní asistent (Vypnuto)',
      preset_auto: '⚡ Auto (Doporučit)',
      preset_auteur: '🎬 Auteur & Vizuální analýza (Mise-en-scène)',
      preset_first_principles: '📐 First Principles (Kód & 3D dekonstrukce)',
      preset_red_team: '🛡️ Red Team & Oponentura hypotéz',
      preset_deep_analysis: '📊 Hloubková analýza v3.1',
      preset_taleb: '📊 Hloubková analýza v3.1',
      preset_assumption_audit: '🔍 Audit předpokladů (Standard)',
      preset_assumption_audit_crisis: '🚨 Audit předpokladů (Krizový režim)',
      preset_meta_analysis: '📑 Meta-analýza (Plná šablona)',
      card_v_resizer_title: 'Tažením změnit výšku panelu',
      toggle_web_tools: 'Web Nástroje',
      toggle_web_tools_title: 'Povolit webové vyhledávání a externí nástroje',
      toggle_rag: 'RAG',
      toggle_rag_title: 'Sémantické vyhledávání z RAG databáze',
      toggle_tts: 'TTS',
      toggle_tts_title: 'Hlasová syntéza (čtení odpovědí)',
      btn_clear_chat_title: 'Vymazat historii relace',

      hero_title: 'AI Assistant Voice CS',
      hero_subtitle: 'Lokální hlasový asistent & 3D technický ředitel',
      chip_inspect_title: 'Prozkoumat scénu a viewport v Blenderu',
      chip_autorig_title: 'Aplikovat Auto-Rig & Skinning (ARMATURE_AUTO)',
      chip_meshdoctor_title: 'Mesh Doctor audit topologie (3D tisk)',
      chip_studio_title: 'Vytvořit produktové studio s nasvícením',

      remove_attachment_title: 'Odebrat přílohu',
      thinking_status: 'Přemýšlím…',
      prompt_placeholder: 'Napište dotaz nebo příkaz pro Blender... (Enter pro odeslání, Shift+Enter pro nový řádek)',
      attach_file_title: 'Připojit dokument pro RAG (PDF, TXT, DOCX)',
      mic_btn_title: 'Hlasový záznam (přepis přes Whisper)',
      prompt_shortcut_hint: 'Enter pro odeslání • Shift+Enter pro nový řádek',
      send_btn_title: 'Odeslat zprávu',
      stop_btn_title: 'Zastavit generování',
      default_doc_prompt: 'Zpracuj tento přiložený dokument.',

      resizer_title_right: 'Tažením změnit šířku pravého panelu',
      inspector_title: '3D VIEWPORT & TELEMETRIE',
      btn_refresh_telemetry_title: 'Obnovit snímek a metriky',
      card_viewport_title: 'ŽIVÝ NÁHLED VIEWPORTU',
      viewport_active: 'Aktivní',
      viewport_offline: 'Offline',
      btn_snapshot: 'Pořídit snímek',
      card_metrics_title: 'METRIKY 3D SCÉNY',
      metric_total_objects: 'Objektů celkem',
      metric_active_mesh: 'Aktivní MESH',
      metric_total_faces: 'Počet polygonů',
      metric_total_verts: 'Počet vrcholů',
      metric_watertight: 'Vodotěsnost',
      metric_bones: 'Kostí kostry',
      metric_yes: 'ANO',
      metric_no: 'NE',
      metric_none: 'Žádný',

      card_quick_actions: 'RYCHLÉ 3D PŘÍKAZY (BLENDER)',
      qa_inspect_title: 'Inspekce viewportu',
      qa_inspect_sub: 'Snímek a sběr telemetrie',
      qa_autorig_title: 'Auto-Rig & Skinning',
      qa_autorig_sub: 'Kostra + ARMATURE_AUTO',
      qa_meshdoctor_title: 'Mesh Doctor Audit',
      qa_meshdoctor_sub: 'Kontrola manifold sítě pro 3D tisk',
      qa_studio_title: 'Produktové studio',
      qa_studio_sub: 'Tříbodové AREA světlo + pozadí',
      qa_shader_title: 'Kartáčovaný kov (Shader)',
      qa_shader_sub: 'Procedurální Principled BSDF strom',
      card_console_title: 'TELEMETRICKÁ KONZOLE',
      btn_clear_console: 'Vymazat',

      modal_rag_title: 'Báze znalostí & RAG dokumenty',
      modal_rag_desc: 'Dokumenty indexované v lokální sémantické paměti (FAISS). Model vyhledává fakta bez cloudu.',
      rag_dropzone_text: 'Klikněte nebo přetáhněte dokumenty sem (PDF, TXT, DOCX, MD)',
      modal_indexed_docs_header: 'Indexované dokumenty:',
      no_indexed_docs: 'Zatím nejsou indexovány žádné dokumenty.',
      btn_delete_doc: 'Odstranit',
      btn_reindex_memory: 'Reindexovat sémantickou paměť',

      modal_settings_title: 'Konfigurace AI asistenta',
      cfg_language: 'Jazyk rozhraní:',
      cfg_temp: 'Kreativita / Teplota:',
      cfg_tokens: 'Maximální počet tokenů:',
      cfg_sysprompt: 'Systémový prompt:',
      btn_reset_defaults: 'Obnovit výchozí nastavení',
      btn_save_settings: 'Uložit nastavení',

      confirm_reset_defaults: 'Opravdu chcete obnovit všechna nastavení rozhraní do výchozího stavu (angličtina, výchozí šířky panelů)?',
      confirm_clear_session: 'Opravdu chcete vymazat historii zpráv této relace?',
      confirm_delete_rag_doc: 'Opravdu chcete odebrat "{name}" z indexu RAG?',
      new_chat_title: 'Nový chat',
      copy_code: 'Kopírovat',
      copied_code: 'Zkopírováno!',
      you: 'Vy',
      stopped_pill: 'Generování zastaveno',
      rag_status_files: 'RAG: {docs} souborů ({chunks} úseků)',
      blender_connected: 'Připojen',
      blender_offline: 'Offline',
      config_saved: 'Konfigurace byla úspěšně uložena.',
      error_save_config: 'Nepodařilo se uložit nastavení',
      error_saving_config: 'Chyba ukládání konfigurace',
      log_session_deleted: 'Relace {id} smazána.',
    }
  };

  const CHIP_PROMPTS = {
    en: {
      chip_inspect: 'Inspect current Blender scene, retrieve object count and viewport capture.',
      chip_autorig: 'Generate an automatic armature skeleton and skinning for the active mesh in Blender.',
      chip_meshdoctor: 'Perform a topology audit of the active model, check non-manifold geometry and 3D print readiness.',
      chip_studio: 'Set up a clean product studio scene in Blender with three-point lighting and backdrop.',
    },
    cs: {
      chip_inspect: 'Prozkoumej aktuální scénu v Blenderu, zjisti počet objektů a pořiď snímek viewportu.',
      chip_autorig: 'Vygeneruj automatickou kostru armature a skinning pro aktivní mesh v Blenderu.',
      chip_meshdoctor: 'Proveď topologický audit aktivního modelu, zkontroluj non-manifold geometrii a připravenost pro 3D tisk.',
      chip_studio: 'Nastav v Blenderu čisté produktové studio s tříbodovým nasvícením a nekonečným pozadím.',
    }
  };

  function t(key, params = {}) {
    const lang = state.language || 'en';
    let str = (I18N[lang] && I18N[lang][key] !== undefined)
      ? I18N[lang][key]
      : ((I18N['en'] && I18N['en'][key] !== undefined) ? I18N['en'][key] : key);
    Object.keys(params).forEach(p => {
      str = str.replace(new RegExp(`\\{${p}\\}`, 'g'), params[p]);
    });
    return str;
  }

  function applyTranslations(lang = 'en') {
    if (lang !== 'en' && lang !== 'cs') lang = 'en';
    document.documentElement.lang = lang;

    // Elements with data-i18n (textContent)
    document.querySelectorAll('[data-i18n]').forEach(elem => {
      const key = elem.dataset.i18n;
      if (I18N[lang] && I18N[lang][key] !== undefined) {
        elem.textContent = I18N[lang][key];
      }
    });

    // Elements with data-i18n-title (title attribute)
    document.querySelectorAll('[data-i18n-title]').forEach(elem => {
      const key = elem.dataset.i18nTitle;
      if (I18N[lang] && I18N[lang][key] !== undefined) {
        elem.setAttribute('title', I18N[lang][key]);
      }
    });

    // Elements with data-i18n-placeholder (placeholder attribute)
    document.querySelectorAll('[data-i18n-placeholder]').forEach(elem => {
      const key = elem.dataset.i18nPlaceholder;
      if (I18N[lang] && I18N[lang][key] !== undefined) {
        elem.setAttribute('placeholder', I18N[lang][key]);
      }
    });

    // Suggestion chips prompt payloads
    document.querySelectorAll('.suggestion-chip').forEach(btn => {
      const chipKey = btn.dataset.chipKey;
      if (chipKey && CHIP_PROMPTS[lang] && CHIP_PROMPTS[lang][chipKey]) {
        btn.dataset.prompt = CHIP_PROMPTS[lang][chipKey];
      }
    });

    // Select dropdown in settings modal
    if (el.cfgLanguage) {
      el.cfgLanguage.value = lang;
    }

    // Keep active preset select value in sync
    if (el.selectPreset && state.selectedPreset) {
      el.selectPreset.value = state.selectedPreset;
    }
  }

  function setLanguage(lang) {
    if (lang !== 'en' && lang !== 'cs') lang = 'en';
    state.language = lang;
    try {
      localStorage.setItem('polygon_language', lang);
    } catch (e) {}
    applyTranslations(lang);
    renderSessionsList();
    refreshBlenderStatus();
    refreshSystemStatus();
    logConsole(lang === 'cs' ? 'Jazyk rozhraní přepnut na češtinu.' : 'Interface language set to English.', 'info');
  }

  const LEGACY_PRESET_MAP = {
    'Vypnuto (Standardní chat)': 'standard',
    'Standard Assistant (Off)': 'standard',
    'Standard Assistant': 'standard',
    'standard': 'standard',
    'Auto (Doporučit)': 'auto',
    'Auto-Select Methodology': 'auto',
    'auto': 'auto',
    'Auteur & Vizuální analýza (Mise-en-scène)': 'auteur',
    'Auteur & Vizuální analýza': 'auteur',
    'Auteur & Visual Style': 'auteur',
    'auteur': 'auteur',
    'First Principles (Kód & 3D dekonstrukce)': 'first_principles',
    'First Principles (Kód & 3D)': 'first_principles',
    'First Principles (3D CAD)': 'first_principles',
    'first_principles': 'first_principles',
    'Red Team & Oponentura hypotéz': 'red_team',
    'Red Team & Oponentura': 'red_team',
    'Red Team & Counter-Analysis': 'red_team',
    'red_team': 'red_team',
    'Hloubková analýza v3.1': 'deep_analysis',
    'Hloubková analýza (Taleb/Munger)': 'deep_analysis',
    'In-Depth Analysis v3.1': 'deep_analysis',
    'deep_analysis': 'deep_analysis',
    'Audit předpokladů (Standard)': 'assumption_audit',
    'Audit předpokladů': 'assumption_audit',
    'Assumption Audit (Standard)': 'assumption_audit',
    'Assumption Audit': 'assumption_audit',
    'assumption_audit': 'assumption_audit',
    'Audit předpokladů (Krizový režim)': 'assumption_audit_crisis',
    'Assumption Audit (Crisis)': 'assumption_audit_crisis',
    'assumption_audit_crisis': 'assumption_audit_crisis',
    'Meta-analýza (Plná šablona)': 'meta_analysis',
    'Meta-analýza': 'meta_analysis',
    'Meta-Analysis (Full Template)': 'meta_analysis',
    'Meta-Analysis': 'meta_analysis',
    'meta_analysis': 'meta_analysis',
  };

  function loadStoredPreferences() {
    try {
      // 1. Language preference (default EN)
      const storedLang = localStorage.getItem('polygon_language') || 'en';
      state.language = (storedLang === 'cs' || storedLang === 'en') ? storedLang : 'en';

      // 2. Sidebar widths
      const storedLeft = localStorage.getItem('polygon_left_sidebar_width');
      if (storedLeft) {
        state.leftSidebarWidth = storedLeft;
        document.documentElement.style.setProperty('--left-sidebar-width', storedLeft);
      }
      const storedRight = localStorage.getItem('polygon_right_sidebar_width');
      if (storedRight) {
        state.rightSidebarWidth = storedRight;
        document.documentElement.style.setProperty('--right-sidebar-width', storedRight);
      }

      // 3. Toggles
      const storedOnline = localStorage.getItem('polygon_online_enabled');
      if (storedOnline !== null) {
        state.onlineMode = storedOnline === 'true';
        if (el.toggleOnline) el.toggleOnline.classList.toggle('active', state.onlineMode);
      }
      const storedRag = localStorage.getItem('polygon_rag_enabled');
      if (storedRag !== null) {
        state.ragEnabled = storedRag === 'true';
        if (el.toggleRag) el.toggleRag.classList.toggle('active', state.ragEnabled);
      }
      const storedTts = localStorage.getItem('polygon_tts_enabled');
      if (storedTts !== null) {
        state.ttsEnabled = storedTts === 'true';
        if (el.toggleTts) el.toggleTts.classList.toggle('active', state.ttsEnabled);
      }

      // 4. Selected preset (canonical ID)
      const rawStoredPreset = localStorage.getItem('polygon_selected_preset');
      const canonicalPreset = LEGACY_PRESET_MAP[rawStoredPreset] || rawStoredPreset;
      state.selectedPreset = canonicalPreset || 'standard';
      if (el.selectPreset) el.selectPreset.value = state.selectedPreset;

      // 5. Inspector card heights (vertical resizers)
      const storedHeights = localStorage.getItem('polygon_inspector_card_heights');
      if (storedHeights) {
        try {
          const heights = JSON.parse(storedHeights);
          Object.keys(heights).forEach(id => {
            const card = document.getElementById(id);
            if (card && heights[id]) {
              card.style.height = heights[id];
            }
          });
        } catch (e) {}
      }
    } catch (e) {
      // Ignore localStorage read errors
    }
  }

  function initSidebarResizers() {
    // Left resizer
    if (el.resizerLeft) {
      let isDraggingLeft = false;

      const onPointerMoveLeft = (e) => {
        if (!isDraggingLeft) return;
        const newWidth = Math.min(Math.max(e.clientX, 200), 500);
        const widthPx = `${newWidth}px`;
        document.documentElement.style.setProperty('--left-sidebar-width', widthPx);
        state.leftSidebarWidth = widthPx;
      };

      const onPointerUpLeft = () => {
        if (!isDraggingLeft) return;
        isDraggingLeft = false;
        document.body.classList.remove('is-resizing-left');
        try {
          localStorage.setItem('polygon_left_sidebar_width', state.leftSidebarWidth);
        } catch (e) {}
        window.removeEventListener('pointermove', onPointerMoveLeft);
        window.removeEventListener('pointerup', onPointerUpLeft);
        window.removeEventListener('pointercancel', onPointerUpLeft);
      };

      el.resizerLeft.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        isDraggingLeft = true;
        document.body.classList.add('is-resizing-left');
        window.addEventListener('pointermove', onPointerMoveLeft);
        window.addEventListener('pointerup', onPointerUpLeft);
        window.addEventListener('pointercancel', onPointerUpLeft);
      });
    }

    // Right resizer
    if (el.resizerRight) {
      let isDraggingRight = false;

      const onPointerMoveRight = (e) => {
        if (!isDraggingRight) return;
        const newWidth = Math.min(Math.max(window.innerWidth - e.clientX, 240), 600);
        const widthPx = `${newWidth}px`;
        document.documentElement.style.setProperty('--right-sidebar-width', widthPx);
        state.rightSidebarWidth = widthPx;
      };

      const onPointerUpRight = () => {
        if (!isDraggingRight) return;
        isDraggingRight = false;
        document.body.classList.remove('is-resizing-right');
        try {
          localStorage.setItem('polygon_right_sidebar_width', state.rightSidebarWidth);
        } catch (e) {}
        window.removeEventListener('pointermove', onPointerMoveRight);
        window.removeEventListener('pointerup', onPointerUpRight);
        window.removeEventListener('pointercancel', onPointerUpRight);
      };

      el.resizerRight.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        isDraggingRight = true;
        document.body.classList.add('is-resizing-right');
        window.addEventListener('pointermove', onPointerMoveRight);
        window.addEventListener('pointerup', onPointerUpRight);
        window.addEventListener('pointercancel', onPointerUpRight);
      });
    }
  }

  function initVerticalResizers() {
    document.querySelectorAll('.card-v-resizer').forEach(resizer => {
      const targetId = resizer.dataset.target;
      const targetCard = targetId ? document.getElementById(targetId) : resizer.closest('.inspector-card');
      if (!targetCard) return;

      let isDragging = false;
      let startY = 0;
      let startHeight = 0;

      const onPointerMove = (e) => {
        if (!isDragging) return;
        const deltaY = e.clientY - startY;
        const newHeight = Math.max(70, Math.min(startHeight + deltaY, 900));
        targetCard.style.height = `${newHeight}px`;
      };

      const onPointerUp = () => {
        if (!isDragging) return;
        isDragging = false;
        resizer.classList.remove('dragging');
        document.body.classList.remove('is-resizing-card');

        try {
          const heights = {};
          document.querySelectorAll('.inspector-card[id]').forEach(card => {
            if (card.style.height) {
              heights[card.id] = card.style.height;
            }
          });
          localStorage.setItem('polygon_inspector_card_heights', JSON.stringify(heights));
        } catch (e) {}

        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', onPointerUp);
        window.removeEventListener('pointercancel', onPointerUp);
      };

      resizer.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        e.stopPropagation();
        isDragging = true;
        startY = e.clientY;
        startHeight = targetCard.getBoundingClientRect().height;
        resizer.classList.add('dragging');
        document.body.classList.add('is-resizing-card');

        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
        window.addEventListener('pointercancel', onPointerUp);
      });
    });
  }

  function resetToDefaults() {
    if (!confirm(t('confirm_reset_defaults'))) return;
    try {
      localStorage.removeItem('polygon_language');
      localStorage.removeItem('polygon_left_sidebar_width');
      localStorage.removeItem('polygon_right_sidebar_width');
      localStorage.removeItem('polygon_inspector_card_heights');
      localStorage.removeItem('polygon_online_enabled');
      localStorage.removeItem('polygon_rag_enabled');
      localStorage.removeItem('polygon_tts_enabled');
      localStorage.removeItem('polygon_selected_preset');
      localStorage.removeItem('polygon_temperature');
      localStorage.removeItem('polygon_max_tokens');
      localStorage.removeItem('polygon_system_prompt');

      state.language = 'en';
      state.leftSidebarWidth = '280px';
      state.rightSidebarWidth = '340px';
      state.onlineMode = true;
      state.ragEnabled = true;
      state.ttsEnabled = false;
      state.selectedPreset = 'standard';

      document.documentElement.style.setProperty('--left-sidebar-width', '280px');
      document.documentElement.style.setProperty('--right-sidebar-width', '340px');
      document.querySelectorAll('.inspector-card[id]').forEach(card => {
        card.style.height = '';
      });

      if (el.toggleOnline) el.toggleOnline.classList.add('active');
      if (el.toggleRag) el.toggleRag.classList.add('active');
      if (el.toggleTts) el.toggleTts.classList.remove('active');
      if (el.selectPreset) el.selectPreset.value = 'standard';

      if (el.cfgTemp) el.cfgTemp.value = 0.7;
      if (el.cfgTokens) el.cfgTokens.value = 1024;
      if (el.cfgSysprompt) el.cfgSysprompt.value = '';
      if (el.cfgLanguage) el.cfgLanguage.value = 'en';

      setLanguage('en');
      closeSettingsModal();
      logConsole('Factory reset complete. Defaults restored (EN).', 'info');
    } catch (err) {
      logConsole(`Reset error: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // HELPER FUNCTIONS: TELEMETRIC LOG
  // ===========================================================================
  const MAX_CONSOLE_LINES = 200;
  function logConsole(message, type = 'info') {
    if (!el.consoleOutput) return;
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    const time = new Date().toLocaleTimeString();
    line.textContent = `[${time}] ${message}`;
    el.consoleOutput.appendChild(line);

    // FIFO DOM limiting
    while (el.consoleOutput.children.length > MAX_CONSOLE_LINES) {
      el.consoleOutput.removeChild(el.consoleOutput.firstElementChild || el.consoleOutput.firstChild);
    }

    el.consoleOutput.scrollTop = el.consoleOutput.scrollHeight;
  }

  // ===========================================================================
  // MARKDOWN RENDERER (LIGHTWEIGHT, SAFE, FAST)
  // ===========================================================================
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Global handler for copying code snippets
  window.copyCode = (btn) => {
    if (!btn) return;
    const code = btn.dataset.code || '';
    const checkSvg = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    const copySvg = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;
    const copyLabel = escapeHtml(t('copy_code'));
    const copiedLabel = escapeHtml(t('copied_code'));

    navigator.clipboard.writeText(code).then(() => {
      btn.innerHTML = `${checkSvg} <span>${copiedLabel}</span>`;
      btn.classList.add('copied');
      setTimeout(() => {
        btn.innerHTML = `${copySvg} <span>${copyLabel}</span>`;
        btn.classList.remove('copied');
      }, 2000);
    }).catch(() => {});
  };

  function renderMarkdown(rawText) {
    if (!rawText) return '';

    // Code blocks extraction with Highlight.js
    const codeBlocks = [];
    let text = rawText.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      const rawCode = code.trim();
      const cleanLang = (lang || '').trim().toLowerCase();
      let highlightedCode = '';

      if (window.hljs) {
        try {
          if (cleanLang && window.hljs.getLanguage(cleanLang)) {
            highlightedCode = window.hljs.highlight(rawCode, { language: cleanLang, ignoreIllegals: true }).value;
          } else {
            const autoRes = window.hljs.highlightAuto(rawCode);
            highlightedCode = autoRes.value;
          }
        } catch (e) {
          highlightedCode = escapeHtml(rawCode);
        }
      } else {
        highlightedCode = escapeHtml(rawCode);
      }

      const displayLang = cleanLang || 'code';
      const copyLabel = escapeHtml(t('copy_code'));
      const copySvg = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;

      codeBlocks.push(
        `<div class="code-block">` +
          `<div class="code-block-header">` +
            `<span class="code-block-lang">${escapeHtml(displayLang)}</span>` +
            `<button class="copy-code-btn" onclick="window.copyCode(this)" data-code="${escapeHtml(rawCode)}">${copySvg} <span>${copyLabel}</span></button>` +
          `</div>` +
          `<pre><code class="hljs ${cleanLang ? `language-${escapeHtml(cleanLang)}` : ''}">${highlightedCode}</code></pre>` +
        `</div>`
      );
      return `@@@CODEBLOCK_${idx}@@@`;
    });

    // Basic formatting
    text = escapeHtml(text);

    // Visual alerts / tool alert boxes
    text = text.replace(/^&gt;\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/gim, (m, alertType, content) => {
      return `<div class="tool-result-box ${alertType.toLowerCase()}"><strong>[${alertType}]</strong> ${content}</div>`;
    });

    // Headers
    text = text.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    text = text.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    text = text.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold & italic
    text = text.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline code
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Lists
    text = text.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    text = text.replace(/<\/ul>\s*<ul>/g, '');

    // Blockquotes
    text = text.replace(/^&gt;\s+(.*)$/gim, '<blockquote>$1</blockquote>');
    text = text.replace(/<\/blockquote>\s*<blockquote>/g, '<br>');

    // Links (strict scheme validation: only http:// and https:// allowed)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, rawUrl) => {
      const trimmedUrl = rawUrl.trim();
      const isSafe = /^https?:\/\//i.test(trimmedUrl);
      const safeHref = isSafe ? escapeHtml(trimmedUrl) : '#';
      return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });

    // Viewport preview snapshot link detection
    text = text.replace(/(\/tmp\/[a-zA-Z0-9_\-]+\.png)/g, (match) => {
      return `<div class="chat-viewport-embed"><img src="/api/blender/viewport-image?t=${Date.now()}" alt="Viewport Screenshot" class="clickable-snapshot" onclick="window.openLightbox(this.src)" /><span class="embed-caption"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg> <span>${match}</span></span></div>`;
    });

    // Paragraph breaks
    text = text.replace(/\n\n+/g, '</p><p>');
    text = `<p>${text}</p>`;
    text = text.replace(/<p><\/p>/g, '');
    text = text.replace(/<p>(<div.*?<\/div>)<\/p>/g, '$1');
    text = text.replace(/<p>(<ul>.*?<\/ul>)<\/p>/g, '$1');
    text = text.replace(/<p>(<blockquote>.*?<\/blockquote>)<\/p>/g, '$1');
    text = text.replace(/<p>(<h[1-3]>.*?<\/h[1-3]>)<\/p>/g, '$1');

    // Restore code blocks
    text = text.replace(/@@@CODEBLOCK_(\d+)@@@/g, (match, idx) => {
      return codeBlocks[Number(idx)] || '';
    });

    return text;
  }

  // Global handler for lightbox preview
  window.openLightbox = (src) => {
    if (el.imageLightbox && el.lightboxImg) {
      el.lightboxImg.src = src;
      el.imageLightbox.style.display = 'flex';
    }
  };

  // ===========================================================================
  // SESSION MANAGEMENT
  // ===========================================================================
  async function loadSessions(targetSelectId = null) {
    try {
      const res = await fetch('/api/sessions');
      if (!res.ok) throw new Error('Error loading sessions');
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
      logConsole(`Error loading sessions: ${err.message}`, 'error');
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
      el.sessionsContainer.innerHTML = `<div style="padding: 12px 14px; font-size: 12px; color: var(--color-text-muted);">${escapeHtml(t('no_sessions'))}</div>`;
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
          <div class="session-item-title">${escapeHtml(s.title || t('unnamed_session'))}</div>
          <div class="session-item-time">${dateStr}</div>
        </div>
        <div class="session-actions">
          <button class="session-action-btn delete-btn" title="${escapeHtml(t('delete_session_title'))}" data-action="delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path><line x1="10" x1="10" y1="11" y2="17"></line><line x1="14" x2="14" y1="11" y2="17"></line></svg>
          </button>
        </div>
      `;

      // Direct click handler on delete button to prevent bubbling issues
      const deleteBtn = item.querySelector('[data-action="delete"]');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          e.preventDefault();
          if (state.isStreaming) {
            logConsole(state.language === 'cs' ? 'Nelze mazat relaci během generování.' : 'Cannot delete session during generation.', 'warn');
            return;
          }
          deleteSession(sid);
        });
      }

      item.addEventListener('click', (e) => {
        if (e.target.closest('[data-action="delete"]')) return;
        if (state.isStreaming) {
          logConsole(state.language === 'cs' ? 'Během generování nelze přepínat relace.' : 'Cannot switch sessions while generation is in progress.', 'warn');
          return;
        }
        selectSession(sid);
      });

      el.sessionsContainer.appendChild(item);
    });
  }

  async function createNewSession() {
    if (state.isStreaming) {
      logConsole('Cannot create a new session while generation is in progress.', 'warn');
      return;
    }
    try {
      const defaultTitle = encodeURIComponent(t('new_chat_title'));
      const res = await fetch(`/api/sessions?title=${defaultTitle}`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      const newSess = await res.json();
      state.sessions.unshift(newSess);
      const sid = newSess.session_id || newSess.id;
      await selectSession(sid);
      renderSessionsList();
      logConsole(`Session created: ${sid}`, 'info');
      el.promptInput.focus();
    } catch (err) {
      logConsole(`Error creating session: ${err.message}`, 'error');
    }
  }

  async function selectSession(sessionId) {
    if (!sessionId) return;

    if (state.isStreaming) {
      logConsole('Cannot switch sessions during generation. Stop generation first.', 'warn');
      return;
    }

    if (state.selectSessionAbortController) {
      state.selectSessionAbortController.abort();
    }
    state.selectSessionAbortController = new AbortController();
    const currentSeq = ++state.selectSessionSeq;

    state.sessionId = sessionId;

    // Update active highlight in sidebar
    document.querySelectorAll('.session-item').forEach(node => {
      node.classList.toggle('active', node.dataset.id === sessionId);
    });

    try {
      const res = await fetch(`/api/sessions/${sessionId}`, {
        signal: state.selectSessionAbortController.signal,
      });
      if (!res.ok) throw new Error('Session not found');
      const data = await res.json();

      // Race condition guard
      if (currentSeq !== state.selectSessionSeq || state.sessionId !== sessionId) {
        return;
      }
      
      const current = state.sessions.find(s => (s.session_id === sessionId || s.id === sessionId));
      if (el.activeSessionTitle) {
        el.activeSessionTitle.textContent = current ? (current.title || t('unnamed_session')) : t('new_chat_title');
      }

      renderMessages(data.messages || []);
    } catch (err) {
      if (err.name === 'AbortError') {
        return;
      }
      logConsole(`Error loading messages: ${err.message}`, 'error');
    }
  }

  async function deleteSession(sessionId) {
    if (!sessionId) return;
    if (state.isStreaming) {
      logConsole(state.language === 'cs' ? 'Nelze mazat relaci během generování.' : 'Cannot delete session while generation is active.', 'warn');
      return;
    }

    // 1. Optimistic UI update: immediately remove from state and re-render sidebar
    const previousSessions = [...state.sessions];
    const wasActive = (state.sessionId === sessionId);
    state.sessions = state.sessions.filter(s => (s.session_id !== sessionId && s.id !== sessionId));
    renderSessionsList();

    // 2. If the deleted session was currently opened, immediately switch
    if (wasActive) {
      state.sessionId = null;
      if (state.sessions.length > 0) {
        const nextFirst = state.sessions[0];
        const nextId = nextFirst.session_id || nextFirst.id;
        selectSession(nextId);
      } else {
        createNewSession();
      }
    }

    // 3. Issue background hard-delete call to backend
    try {
      const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      logConsole(t('log_session_deleted', { id: sessionId }), 'warn');
    } catch (err) {
      logConsole(`Delete error: ${err.message}`, 'error');
      // Rollback optimistic removal on network error
      state.sessions = previousSessions;
      renderSessionsList();
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
      if (!res.ok) throw new Error('Failed to rename');
      const target = state.sessions.find(s => (s.session_id === sessionId || s.id === sessionId));
      if (target) target.title = clean;
      renderSessionsList();
      logConsole(`Session renamed to: ${clean}`, 'info');
    } catch (err) {
      logConsole(`Rename error: ${err.message}`, 'error');
    }
  }

  async function clearCurrentSession() {
    if (!state.sessionId) return;
    if (!confirm(t('confirm_clear_session'))) return;
    try {
      const res = await fetch(`/api/sessions/${state.sessionId}/messages`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to clear messages');
      renderMessages([]);
      logConsole(`Session messages cleared: ${state.sessionId}`, 'warn');
    } catch (err) {
      logConsole(`Error: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // MESSAGE RENDERING IN CHAT VIEWPORT
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
    const authorName = isUser ? t('you') : 'Polygon Beater Core';

    card.innerHTML = `
      <div class="message-card-header">
        <div class="message-avatar">${avatarLetter}</div>
        <span class="message-author">${escapeHtml(authorName)}</span>
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

    // Default prompt when sending attachment with empty input
    const effectivePrompt = (rawPrompt || (state.attachedFile
      ? t('default_doc_prompt')
      : ''));

    // Process attachment if present
    if (state.attachedFile) {
      const uploaded = await uploadPendingAttachment();
      if (!uploaded) return;
    }

    const promptText = effectivePrompt;
    el.promptInput.value = '';
    el.promptInput.style.height = 'auto';

    // Ensure valid session exists
    if (!state.sessionId) {
      if (state.sessions && state.sessions.length > 0) {
        const first = state.sessions[0];
        state.sessionId = first.session_id || first.id;
      } else {
        try {
          const defaultTitle = encodeURIComponent(t('new_chat_title'));
          const sRes = await fetch(`/api/sessions?title=${defaultTitle}`, { method: 'POST' });
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

    // Append user card
    appendMessageCard('user', promptText, false);

    // Prepare assistant response card
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
        language: state.language || 'en',
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
        buffer = lines.pop();

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
              logConsole(`Methodology: ${data.content}`, 'info');
            } else if (data.type === 'done') {
              fullText = data.content || fullText;
              bodyEl.innerHTML = renderMarkdown(fullText);
              scrollToBottom();
            } else if (data.type === 'error') {
              bodyEl.innerHTML += `<div class="error-badge"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>${escapeHtml(data.content)}</span></div>`;
              logConsole(`Error: ${data.content}`, 'error');
            }
          } catch (e) {
            // parsing error fallback
          }
        }
      }

      // Auto rename session on first prompt
      const current = state.sessions.find(s => (s.session_id === state.sessionId || s.id === state.sessionId));
      if (current && (current.title === 'Nový chat' || current.title === 'New chat' || current.title === t('new_chat_title') || current.title === 'Nepojmenovaná relace' || current.title === t('unnamed_session'))) {
        const autoTitle = promptText.slice(0, 32).trim() + (promptText.length > 32 ? '…' : '');
        renameSession(state.sessionId, autoTitle);
      }

      // Optional TTS voice playback
      if (state.ttsEnabled && fullText) {
        speakText(fullText);
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        logConsole('Generation interrupted by user.', 'warn');
        bodyEl.innerHTML += `<div class="tool-status-pill abort-pill"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="5" y="5" rx="2"></rect></svg> <span>${escapeHtml(t('stopped_pill'))}</span></div>`;
      } else {
        logConsole(`Backend communication error: ${err.message}`, 'error');
        bodyEl.innerHTML += `<div class="error-badge"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>Connection Error: ${escapeHtml(err.message)}</span></div>`;
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
      // Ignore
    }
  }

  function updateStreamingUi(isStreaming) {
    if (el.btnSend && el.btnStop && el.liveStatusBadge) {
      el.btnSend.style.display = isStreaming ? 'none' : 'flex';
      el.btnStop.style.display = isStreaming ? 'flex' : 'none';
      el.liveStatusBadge.style.display = isStreaming ? 'inline-flex' : 'none';
      if (isStreaming) {
        el.liveStatusText.textContent = t('thinking_status');
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
  // RAG ATTACHMENTS & UPLOAD
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
      logConsole(`Uploading document to RAG: ${state.attachedFile.name}...`, 'info');
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
          // Keep status text
        }
        throw new Error(`HTTP ${res.status}: ${detail}`);
      }
      const data = await res.json();
      if (!Number.isInteger(data.chunks_indexed) || data.chunks_indexed < 1) {
        throw new Error('No indexable text found in file.');
      }
      logConsole(`Indexing complete: ${data.filename} (${data.chunks_indexed} chunks)`, 'info');
      setAttachedFile(null);
      await refreshSystemStatus();
      return true;
    } catch (err) {
      logConsole(`Attachment indexing error: ${err.message}`, 'error');
      return false;
    }
  }

  // ===========================================================================
  // 3D BLENDER BRIDGE & TELEMETRY
  // ===========================================================================
  async function refreshBlenderStatus() {
    try {
      const res = await fetch('/api/blender/status');
      if (!res.ok) return;
      const data = await res.json();
      state.blenderConnected = Boolean(data.connected);

      if (el.blenderIndicator && el.blenderStatusText) {
        el.blenderIndicator.className = `status-indicator ${data.connected ? 'online' : 'offline'}`;
        el.blenderStatusText.textContent = `Blender: ${data.connected ? t('blender_connected') : t('blender_offline')}`;
      }

      if (el.viewportBadge) {
        el.viewportBadge.className = `card-badge ${data.connected ? 'badge-online' : 'badge-offline'}`;
        el.viewportBadge.textContent = data.connected ? t('viewport_active') : t('viewport_offline');
      }
    } catch (e) {
      if (el.blenderIndicator && el.blenderStatusText) {
        el.blenderIndicator.className = 'status-indicator offline';
        el.blenderStatusText.textContent = `Blender: ${t('blender_offline')}`;
      }
    }
  }

  async function takeBlenderInspection() {
    logConsole('Requesting viewport inspection and telemetry...', 'info');
    try {
      const res = await fetch('/api/blender/inspect', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      if (data.status === 'error') {
        throw new Error(data.detail || data.message || data.error || 'Blender inspection failed.');
      }
      
      // Update snapshot with cache buster
      if (el.viewportSnapshotImg) {
        el.viewportSnapshotImg.src = `/api/blender/viewport-image?t=${Date.now()}`;
      }

      // Update telemetry metrics
      updateTelemetryMetrics(data);
      const metrics = data.scene_metrics || data;
      const activeName = metrics.active_object?.name || metrics.active_object || t('metric_none');
      logConsole(`Inspection done: ${metrics.total_objects ?? metrics.objects_count ?? 0} objects, active: ${activeName}`, 'info');
    } catch (err) {
      logConsole(`Blender inspection error: ${err.message}`, 'error');
    }
  }

  function updateTelemetryMetrics(data) {
    if (!data) return;
    const metrics = data.scene_metrics || data;
    const activeObject = metrics.active_object;
    if (el.valTotalObjects) el.valTotalObjects.textContent = metrics.total_objects ?? metrics.objects_count ?? '-';
    if (el.valActiveMesh) el.valActiveMesh.textContent = activeObject?.name || activeObject || t('metric_none');
    const faces = activeObject?.polygons ?? metrics.faces_count;
    const vertices = activeObject?.vertices ?? metrics.vertices_count;
    if (el.valTotalFaces) el.valTotalFaces.textContent = faces != null ? Number(faces).toLocaleString() : '-';
    if (el.valTotalVerts) el.valTotalVerts.textContent = vertices != null ? Number(vertices).toLocaleString() : '-';
    
    if (el.valWatertight) {
      if (data.watertight !== undefined) {
        el.valWatertight.textContent = data.watertight ? t('metric_yes') : t('metric_no');
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
    logConsole(`Executing 3D operation: ${actionName}...`, 'info');
    try {
      const options = { method: 'POST' };
      if (bodyObj) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(bodyObj);
      }
      const res = await fetch(endpoint, options);
      const data = await res.json();
      logConsole(`Result [${actionName}]: ${JSON.stringify(data)}`, 'info');

      // Refresh snapshot and telemetry
      setTimeout(takeBlenderInspection, 500);
    } catch (err) {
      logConsole(`Error during operation ${actionName}: ${err.message}`, 'error');
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
        el.modalDocsList.innerHTML = `<div style="color: var(--color-text-muted); font-size: 13px;">${escapeHtml(t('no_indexed_docs'))}</div>`;
        return;
      }

      el.modalDocsList.innerHTML = '';
      docs.forEach(doc => {
        const item = document.createElement('div');
        item.className = 'indexed-doc-item';

        const title = document.createElement('div');
        title.className = 'doc-item-title';
        title.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" x2="8" y1="13" y2="13"></line><line x1="16" x2="8" y1="17" y2="17"></line><line x1="10" x2="8" y1="9" y2="9"></line></svg> <span>${escapeHtml(doc)}</span>`;

        const removeButton = document.createElement('button');
        removeButton.className = 'doc-delete-btn';
        removeButton.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg> <span>${escapeHtml(t('btn_delete_doc'))}</span>`;
        removeButton.addEventListener('click', () => window.deleteRagDoc(doc));

        item.append(title, removeButton);
        el.modalDocsList.appendChild(item);
      });

    } catch (err) {
      logConsole(`Error loading RAG documents: ${err.message}`, 'error');
    }
  }

  window.deleteRagDoc = async (docName) => {
    if (!confirm(t('confirm_delete_rag_doc', { name: docName }))) return;
    try {
      const res = await fetch(`/api/rag/documents/${encodeURIComponent(docName)}`, { method: 'DELETE' });
      if (res.ok) {
        logConsole(`Document "${docName}" removed.`, 'info');
        await loadRagDocuments();
        await refreshSystemStatus();
      }
    } catch (e) {
      logConsole(`Delete error: ${e.message}`, 'error');
    }
  };

  async function reindexAllMemory() {
    logConsole('Triggering semantic memory & session reindexing...', 'info');
    try {
      const res = await fetch('/api/rag/memory/reindex', { method: 'POST' });
      const data = await res.json();
      logConsole(`Reindexing complete: ${JSON.stringify(data.result || data)}`, 'info');
      await refreshSystemStatus();
    } catch (e) {
      logConsole(`Reindex error: ${e.message}`, 'error');
    }
  }

  // ===========================================================================
  // SETTINGS MODAL & PERSISTENCE
  // ===========================================================================
  async function openSettingsModal() {
    if (!el.modalSettings) return;
    el.modalSettings.style.display = 'flex';
    if (el.cfgLanguage) {
      el.cfgLanguage.value = state.language;
    }
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      const cfg = data.config || {};
      const llama = cfg.llama || {};

      if (el.cfgTemp) el.cfgTemp.value = llama.temperature ?? 0.7;
      if (el.cfgTokens) el.cfgTokens.value = llama.max_tokens ?? 1024;
      if (el.cfgSysprompt) el.cfgSysprompt.value = llama.system_prompt ?? data.default_system_prompt ?? '';
    } catch (e) {
      logConsole(`Error loading config: ${e.message}`, 'error');
    }
  }

  function closeSettingsModal() {
    if (el.modalSettings) el.modalSettings.style.display = 'none';
  }

  async function saveSettings() {
    try {
      if (el.cfgLanguage) {
        setLanguage(el.cfgLanguage.value);
      }
      const payload = {
        temperature: parseFloat(el.cfgTemp.value) || 0.7,
        max_tokens: parseInt(el.cfgTokens.value, 10) || 1024,
        system_prompt: el.cfgSysprompt.value,
      };

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(t('error_save_config'));
      logConsole(t('config_saved'), 'info');
      closeSettingsModal();
    } catch (err) {
      logConsole(`${t('error_saving_config')}: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // SYSTEM STATUS POLL
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
        el.ragStatusText.textContent = t('rag_status_files', { docs: docCount, chunks: chunkCount });
      }

      // Presets catalog & bilingual synchronization
      if (el.selectPreset) {
        const targetVal = state.selectedPreset || el.selectPreset.value;
        const currentLang = state.language || 'en';

        if (data.presets_catalog) {
          const catalogList = Array.isArray(data.presets_catalog)
            ? data.presets_catalog
            : Object.values(data.presets_catalog);

          catalogList.forEach(item => {
            if (!item || !item.id) return;
            const label = (currentLang === 'cs') ? (item.name_cs || item.name_en) : (item.name_en || item.name_cs);
            let opt = Array.from(el.selectPreset.options).find(o => o.value === item.id);
            if (opt) {
              opt.textContent = label;
            } else {
              opt = document.createElement('option');
              opt.value = item.id;
              opt.textContent = label;
              el.selectPreset.appendChild(opt);
            }
          });
        }

        const canonicalTarget = LEGACY_PRESET_MAP[targetVal] || targetVal;
        if (canonicalTarget && Array.from(el.selectPreset.options).some(o => o.value === canonicalTarget)) {
          el.selectPreset.value = canonicalTarget;
          state.selectedPreset = canonicalTarget;
        }
      }
    } catch (e) {
      // Ignore
    }
  }

  // ===========================================================================
  // VOICE RECORDING (MIC / SPEECH-TO-TEXT) & TTS
  // ===========================================================================
  async function toggleMicrophoneRecording() {
    if (state.isStreaming) {
      logConsole('Cannot record audio while generation is in progress.', 'warn');
      return;
    }

    if (state.transcriptionAbortController) {
      state.transcriptionAbortController.abort();
      logConsole('Voice transcription cancelled.', 'warn');
      return;
    }

    if (state.isRecording) {
      // Stop recording
      if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
        state.mediaRecorder.stop();
      }
      state.isRecording = false;
      el.btnMic.classList.remove('recording');
      logConsole('Voice recording stopped.', 'info');
    } else {
      // Start recording
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
          logConsole(`Audio recorded (${Math.round(audioBlob.size / 1024)} kB). Transcribing...`, 'info');
          await transcribeRecordedAudio(audioBlob);
        };

        state.mediaRecorder.onerror = () => {
          stream.getTracks().forEach(track => track.stop());
          state.audioChunks = [];
          state.isRecording = false;
          el.btnMic.classList.remove('recording');
          logConsole('Microphone recording failed.', 'error');
        };

        state.mediaRecorder.start();
        state.isRecording = true;
        el.btnMic.classList.add('recording');
        logConsole('Voice input active (speak into microphone)...', 'info');
      } catch (err) {
        state.audioChunks = [];
        logConsole(`Microphone permission denied: ${err.message}`, 'warn');
      }
    }
  }

  async function transcribeRecordedAudio(audioBlob) {
    if (!audioBlob.size) {
      logConsole('Audio recording contains no data.', 'warn');
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
      logConsole(`Unsupported recording format: ${audioBlob.type || 'unknown'}`, 'error');
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
          // Keep status text
        }
        throw new Error(`HTTP ${response.status}: ${detail}`);
      }
      const data = await response.json();
      const transcript = typeof data.text === 'string' ? data.text.trim() : '';
      if (!transcript) {
        logConsole('No speech recognized in recording.', 'warn');
        return;
      }
      logConsole(`Speech transcribed: "${transcript}"`, 'info');
      el.promptInput.value = transcript;
      await sendMessage();
    } catch (err) {
      if (err.name === 'AbortError') {
        logConsole('Voice transcription was cancelled.', 'warn');
      } else {
        logConsole(`Transcription error: ${err.message}`, 'error');
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
    utterance.lang = state.language === 'cs' ? 'cs-CZ' : 'en-US';
    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  }

  // ===========================================================================
  // EVENT LISTENERS & SETUP
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

    // Rename session on title blur or enter
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

    // New conversation button
    if (el.btnNewChat) el.btnNewChat.addEventListener('click', createNewSession);

    // Filter sessions search input
    if (el.sessionSearch) {
      el.sessionSearch.addEventListener('input', (e) => {
        renderSessionsList(e.target.value);
      });
    }

    // Clear session chat
    if (el.btnClearChat) el.btnClearChat.addEventListener('click', clearCurrentSession);

    // Preset selector change
    if (el.selectPreset) {
      el.selectPreset.addEventListener('change', (e) => {
        state.selectedPreset = e.target.value;
        try {
          localStorage.setItem('polygon_selected_preset', state.selectedPreset);
        } catch (err) {}
        logConsole(`Methodology: ${state.selectedPreset}`, 'info');
      });
    }

    // Toggles with localStorage persistence
    if (el.toggleOnline) {
      el.toggleOnline.addEventListener('click', () => {
        state.onlineMode = !state.onlineMode;
        el.toggleOnline.classList.toggle('active', state.onlineMode);
        try {
          localStorage.setItem('polygon_online_enabled', state.onlineMode ? 'true' : 'false');
        } catch (err) {}
        logConsole(`Web Tools: ${state.onlineMode ? 'ON' : 'OFF'}`, 'info');
      });
    }

    if (el.toggleRag) {
      el.toggleRag.addEventListener('click', () => {
        state.ragEnabled = !state.ragEnabled;
        el.toggleRag.classList.toggle('active', state.ragEnabled);
        try {
          localStorage.setItem('polygon_rag_enabled', state.ragEnabled ? 'true' : 'false');
        } catch (err) {}
        logConsole(`RAG: ${state.ragEnabled ? 'ON' : 'OFF'}`, 'info');
      });
    }

    if (el.toggleTts) {
      el.toggleTts.addEventListener('click', () => {
        state.ttsEnabled = !state.ttsEnabled;
        el.toggleTts.classList.toggle('active', state.ttsEnabled);
        try {
          localStorage.setItem('polygon_tts_enabled', state.ttsEnabled ? 'true' : 'false');
        } catch (err) {}
        logConsole(`TTS Voice: ${state.ttsEnabled ? 'ON' : 'OFF'}`, 'info');
      });
    }

    // File attachments
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

    // Microphone toggle
    if (el.btnMic) el.btnMic.addEventListener('click', toggleMicrophoneRecording);

    // 3D Blender actions
    if (el.btnTakeSnapshot) el.btnTakeSnapshot.addEventListener('click', takeBlenderInspection);
    if (el.btnRefreshTelemetry) el.btnRefreshTelemetry.addEventListener('click', () => {
      refreshBlenderStatus();
      takeBlenderInspection();
    });

    if (el.btnQuickInspect) el.btnQuickInspect.addEventListener('click', takeBlenderInspection);
    if (el.btnQuickAutorig) el.btnQuickAutorig.addEventListener('click', () => executeQuick3DAction('/api/blender/auto-rig', 'Auto-Rig & Skinning'));
    if (el.btnQuickMeshdoctor) el.btnQuickMeshdoctor.addEventListener('click', () => executeQuick3DAction('/api/blender/mesh-doctor', 'Mesh Doctor Audit'));
    if (el.btnQuickStudio) el.btnQuickStudio.addEventListener('click', () => executeQuick3DAction('/api/blender/product-studio', 'Product Studio'));
    if (el.btnQuickShader) el.btnQuickShader.addEventListener('click', () => executeQuick3DAction('/api/blender/procedural-shader', 'Brushed Metal Shader'));

    if (el.btnClearConsole) {
      el.btnClearConsole.addEventListener('click', () => {
        if (el.consoleOutput) el.consoleOutput.innerHTML = '';
      });
    }

    // Viewport image zoom on click
    if (el.viewportSnapshotImg) {
      el.viewportSnapshotImg.addEventListener('click', () => {
        window.openLightbox(el.viewportSnapshotImg.src);
      });
    }

    // Modals open/close
    if (el.btnOpenRag) el.btnOpenRag.addEventListener('click', openRagModal);
    if (el.btnCloseRagModal) el.btnCloseRagModal.addEventListener('click', closeRagModal);
    if (el.btnOpenSettings) el.btnOpenSettings.addEventListener('click', openSettingsModal);
    if (el.btnCloseSettingsModal) el.btnCloseSettingsModal.addEventListener('click', closeSettingsModal);
    if (el.btnSaveSettings) el.btnSaveSettings.addEventListener('click', saveSettings);
    if (el.btnResetDefaults) el.btnResetDefaults.addEventListener('click', resetToDefaults);
    if (el.btnReindexMemory) el.btnReindexMemory.addEventListener('click', reindexAllMemory);

    // Language switcher in settings
    if (el.cfgLanguage) {
      el.cfgLanguage.addEventListener('change', (e) => {
        setLanguage(e.target.value);
      });
    }

    // Close modals when clicking backdrop
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

    // Drag & drop for RAG modal
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
          logConsole(`Uploading "${file.name}" via drag-and-drop...`, 'info');
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
          logConsole(`Uploading "${file.name}"...`, 'info');
          const res = await fetch('/api/rag/upload', { method: 'POST', body: formData });
          if (res.ok) {
            await loadRagDocuments();
            await refreshSystemStatus();
          }
        }
      });
    }

    // Global keyboard shortcuts
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
  // APPLICATION INIT
  // ===========================================================================
  async function init() {
    loadStoredPreferences();
    initSidebarResizers();
    initVerticalResizers();
    applyTranslations(state.language);
    setupEventListeners();

    logConsole(state.language === 'cs' ? 'Inicializuji Polygon Beater Web UI klienta...' : 'Initializing Polygon Beater Web UI client...', 'info');
    await loadSessions();
    await refreshSystemStatus();
    await refreshBlenderStatus();

    // Regular Blender polling interval (8s)
    state.blenderPollInterval = setInterval(refreshBlenderStatus, 8000);
    logConsole(state.language === 'cs' ? 'Polygon Beater klient plně připraven k práci.' : 'Polygon Beater client ready.', 'info');
  }

  // Run upon DOM readiness
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
