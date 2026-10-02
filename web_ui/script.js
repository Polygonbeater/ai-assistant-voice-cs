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
    activeRightTab: '3d',

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

    // Tools Inspector & Registry
    toolsConfig: {},
    toolsRegistry: [],
  };

  // ===========================================================================
  // TOOLS REGISTRY (22 Registered Tools)
  // ===========================================================================
  const TOOLS_REGISTRY = [
    // Web & Rešerše (3)
    {
      name: 'search_web',
      category: 'web',
      title_cs: 'Webové vyhledávání (DuckDuckGo)',
      title_en: 'Web Search (DuckDuckGo)',
      desc_cs: 'Živé online vyhledávání na internetu pro aktuální zprávy, čerstvé události a fakta v reálném čase.',
      desc_en: 'Live web search for breaking news, real-time events, documentation, and live facts.',
      requires_blender: false,
    },
    {
      name: 'query_local_rag',
      category: 'web',
      title_cs: 'Lokální báze dokumentů (RAG)',
      title_en: 'Local Document Base (RAG)',
      desc_cs: 'Sémantické vyhledávání v lokálně nahraných dokumentech (PDF, DOCX, texty) pomocí FAISS vektorové databáze.',
      desc_en: 'Semantic search across locally uploaded documents (PDF, DOCX, code) using FAISS vector database.',
      requires_blender: false,
    },
    {
      name: 'query_memory_rag',
      category: 'web',
      title_cs: 'Sémantická paměť konverzací',
      title_en: 'Semantic Conversation Memory',
      desc_cs: 'Prohledávání dlouhodobé sémantické paměti minulých rozhovorů s uživatelem (dohody, parametry, skripty).',
      desc_en: 'Retrieval from persistent semantic long-term memory of previous user sessions and preferences.',
      requires_blender: false,
    },

    // Systém & Vision (1)
    {
      name: 'analyze_viewport_image',
      category: 'system',
      title_cs: 'Multimodální analýza viewportu',
      title_en: 'Viewport Vision Analysis',
      desc_cs: 'Pořízení snímku obrazovky nebo 3D viewportu a jeho detailní multimodální kognitivní analýza.',
      desc_en: 'Capturing viewport screenshot and performing deep multimodal vision understanding.',
      requires_blender: false,
    },

    // 3D & Blender (18)
    {
      name: 'execute_blender_code',
      category: '3d',
      title_cs: 'Spuštění Python skriptu (bpy)',
      title_en: 'Execute Blender Script (bpy)',
      desc_cs: 'Spuštění libovolného Python skriptu přímo v běžící instanci Blenderu s automatickou opravou chyb.',
      desc_en: 'Direct execution of Python/bpy scripts inside active Blender instance with self-healing loop.',
      requires_blender: true,
    },
    {
      name: 'inspect_blender_scene',
      category: '3d',
      title_cs: 'Inspekce 3D scény',
      title_en: 'Inspect 3D Scene',
      desc_cs: 'Získání detailního přehledu o scéně v Blenderu: hierarchie objektů, počty polygonů, materiály a kamery.',
      desc_en: 'Detailed inspection of Blender scene hierarchy, polygon counts, materials, and active cameras.',
      requires_blender: true,
    },
    {
      name: 'mesh_doctor_audit',
      category: '3d',
      title_cs: 'Mesh Doctor - Audit geometrie',
      title_en: 'Mesh Doctor Geometry Audit',
      desc_cs: 'Kompletní geometrický a topologický audit 3D meshů (non-manifold hrany, n-gony, překryté vertexy).',
      desc_en: 'Comprehensive geometric topology audit (non-manifold edges, n-gons, overlapping vertices).',
      requires_blender: true,
    },
    {
      name: 'mesh_doctor_repair',
      category: '3d',
      title_cs: 'Mesh Doctor - Automatická oprava',
      title_en: 'Mesh Doctor Auto-Repair',
      desc_cs: 'Automatické čištění a chirurgická oprava mesh defektů (sloučení vrcholů, recalculate normals, planarizace).',
      desc_en: 'Automated mesh cleanup and repair (merge by distance, recalculate normals, planarization).',
      requires_blender: true,
    },
    {
      name: 'create_product_studio',
      category: '3d',
      title_cs: '3D Produktové studio & nasvícení',
      title_en: '3D Product Studio & Lighting',
      desc_cs: 'Automatické vybudování fotorealistického 3D produktového studia (bezešvé pozadí cyklorámy, 3-bodové světlo).',
      desc_en: 'Automated photorealistic product studio setup (seamless cyclorama backdrop, 3-point key/fill/rim lights).',
      requires_blender: true,
    },
    {
      name: 'create_procedural_shader',
      category: '3d',
      title_cs: 'Procedurální PBR shadery',
      title_en: 'Procedural PBR Shaders',
      desc_cs: 'Vytvoření fotorealistického procedurálního PBR materiálu pomocí Shader Nodes (kov, autolak, sklo, plast).',
      desc_en: 'Generation of photorealistic procedural PBR materials via Shader Nodes (metal, car paint, glass, plastic).',
      requires_blender: true,
    },
    {
      name: 'uv_texel_audit',
      category: '3d',
      title_cs: 'Audit UV map & hustoty texelů',
      title_en: 'UV Texel Density Audit',
      desc_cs: 'Hloubková kontrola UV map a konzistence hustoty texelů (px/m) napříč všemi objekty scény.',
      desc_en: 'In-depth inspection of UV maps and texel density consistency (px/m) across scene meshes.',
      requires_blender: true,
    },
    {
      name: 'smart_uv_pack',
      category: '3d',
      title_cs: 'Smart UV Unwrap & Pack',
      title_en: 'Smart UV Unwrap & Pack',
      desc_cs: 'Inteligentní automatické rozbalení a optimální sbalení UV ostrovů bez překryvů s nastaveným okrajem.',
      desc_en: 'Intelligent automated unwrapping and optimal packing of UV islands with custom margins.',
      requires_blender: true,
    },
    {
      name: 'generate_parametric_model',
      category: '3d',
      title_cs: 'Parametrické generování modelů',
      title_en: 'Parametric Model Generator',
      desc_cs: 'Procedurální parametrické generování 3D modelů (mechanické krabičky, ozubená kola, schodiště, rámy).',
      desc_en: 'Procedural parametric generation of 3D models (enclosures, gears, staircases, structural frames).',
      requires_blender: true,
    },
    {
      name: 'apply_modifier_stack',
      category: '3d',
      title_cs: 'Správa stacku modifikátorů',
      title_en: 'Modifier Stack Management',
      desc_cs: 'Přidání a konfigurace modifikátorů (Subdivision Surface, Bevel, Boolean, Mirror, Solidify, Array).',
      desc_en: 'Configuration and chaining of mesh modifiers (Subdivision, Bevel, Boolean, Mirror, Solidify, Array).',
      requires_blender: true,
    },
    {
      name: 'create_geometry_nodes_bridge',
      category: '3d',
      title_cs: 'Geometry Nodes procedurální síť',
      title_en: 'Geometry Nodes Bridge',
      desc_cs: 'Vygenerování a propojení stromu procedurálních Geometry Nodes (distribuce instancí, křivky, pole).',
      desc_en: 'Procedural generation and wiring of Geometry Nodes modifier graphs (scattering, curves, mesh arrays).',
      requires_blender: true,
    },
    {
      name: 'apply_fcurve_animation',
      category: '3d',
      title_cs: 'Parametrická F-Curve animace',
      title_en: 'F-Curve Parametric Animation',
      desc_cs: 'Vytvoření parametrické animace objektů, kamer nebo světel pomocí klíčových snímků a interpolačních křivek.',
      desc_en: 'Creation of parametric keyframe animation with mathematical interpolation curves and noise modifiers.',
      requires_blender: true,
    },
    {
      name: 'create_motion_node_setup',
      category: '3d',
      title_cs: 'Motion Nodes procedurální pohyb',
      title_en: 'Motion Nodes Kinematics',
      desc_cs: 'Pokročilá procedurální animace pomocí animačních uzlů a kinetických driverů (cyklická rotace, drift).',
      desc_en: 'Advanced procedural kinetics and mathematical drivers (continuous rotation, bobbing, kinetic drift).',
      requires_blender: true,
    },
    {
      name: 'setup_blueprint_reference',
      category: '3d',
      title_cs: 'Ustavení referenčních blueprintů',
      title_en: 'Technical Blueprint References',
      desc_cs: 'Načtení a přesné ustavení technických výkresů nebo referenčních obrázků do ortografických rovin X/Y/Z.',
      desc_en: 'Placement and alignment of technical drawings or reference images onto orthographic planes.',
      requires_blender: true,
    },
    {
      name: 'vectorize_image_to_3d',
      category: '3d',
      title_cs: 'Vektorizace 2D grafiky do 3D',
      title_en: '2D to 3D Vectorization',
      desc_cs: 'Převedení 2D bitmapového obrázku nebo loga na čisté 3D křivky a polygonální modely s hloubkou a zkosením.',
      desc_en: 'Conversion of 2D bitmap logos or drawings into clean extruded 3D curves and beveled geometry.',
      requires_blender: true,
    },
    {
      name: 'setup_compositor',
      category: '3d',
      title_cs: 'Compositor post-processing',
      title_en: 'Compositor Post-Processing',
      desc_cs: 'Nastavení post-processing nodů v Blender Compositoru (glare bloom, chromatická aberace, vinětace).',
      desc_en: 'Setup of post-processing nodes in Blender Compositor (glare bloom, chromatic aberration, vignette).',
      requires_blender: true,
    },
    {
      name: 'generate_local_ai_mesh',
      category: '3d',
      title_cs: 'Lokální AI Mesh generátor',
      title_en: 'Local AI Mesh Generator',
      desc_cs: 'Generování 3D modelů pomocí lokálních AI difuzních a rekonstrukčních modelů z referenčního obrázku.',
      desc_en: 'Neural 3D mesh generation using local AI reconstruction models from image reference.',
      requires_blender: true,
    },
    {
      name: 'auto_rig_and_skin',
      category: '3d',
      title_cs: 'Auto-Rigging & Skinning koster',
      title_en: 'Auto-Rigging & Skinning',
      desc_cs: 'Automatické vytvoření armatury (kostry) a skinning zvoleného mesh modelu s automatickými vahami.',
      desc_en: 'Automatic generation of skeletal armature and vertex group skinning with automatic weights.',
      requires_blender: true,
    },
  ];

  state.toolsRegistry = TOOLS_REGISTRY;

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

    // Inspector Tabs & Panes
    tabBtn3d: document.getElementById('tab-btn-3d'),
    tabBtnResearch: document.getElementById('tab-btn-research'),
    tabBtnAgent: document.getElementById('tab-btn-agent'),
    pane3d: document.getElementById('pane-3d'),
    paneResearch: document.getElementById('pane-research'),
    paneAgent: document.getElementById('pane-agent'),

    // Research Feeds
    researchSourcesList: document.getElementById('research-sources-list'),
    badgeResearchCount: document.getElementById('badge-research-count'),
    ragSnippetsList: document.getElementById('rag-snippets-list'),
    badgeRagCount: document.getElementById('badge-rag-count'),
    btnOpenKnowledgeFromTab: document.getElementById('btn-open-knowledge-from-tab'),

    // Agent Steps
    agentStepsTimeline: document.getElementById('agent-steps-timeline'),
    btnClearAgentSteps: document.getElementById('btn-clear-agent-steps'),

    // Chat & Tools
    activeSessionTitle: document.getElementById('active-session-title'),
    btnTools: document.getElementById('btn-tools'),
    toolsCountText: document.getElementById('tools-count-text'),
    modalTools: document.getElementById('modal-tools'),
    btnCloseToolsModal: document.getElementById('btn-close-tools-modal'),
    btnEnableAllTools: document.getElementById('btn-enable-all-tools'),
    btnDisableAllTools: document.getElementById('btn-disable-all-tools'),
    btnResetToolsDefaults: document.getElementById('btn-reset-tools-defaults'),
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
    btnProofread: document.getElementById('btn-proofread'),
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

    // Quick Actions & 3D Workspace
    cardActions: document.getElementById('card-actions'),
    qaOfflineBanner: document.getElementById('qa-offline-banner'),
    btnQuickInspect: document.getElementById('btn-qa-inspect-scene'),
    btnQuickAutorig: document.getElementById('btn-qa-autorig'),
    btnQuickMeshdoctor: document.getElementById('btn-qa-mesh-audit'),
    btnQuickStudio: document.getElementById('btn-qa-studio'),
    btnQuickShader: document.getElementById('btn-qa-shader'),

    // Console
    consoleOutput: document.getElementById('console-output'),
    btnClearConsole: document.getElementById('btn-clear-console'),

    // Blender Code Executor Modal
    modalBlenderCode: document.getElementById('modal-blender-code'),
    btnCloseBlenderCodeModal: document.getElementById('btn-close-blender-code-modal'),
    blenderCodeInput: document.getElementById('blender-code-input'),
    blenderCodeOutput: document.getElementById('blender-code-output'),
    blenderCodeOutputText: document.getElementById('blender-code-output-text'),
    btnSendCodeChat: document.getElementById('btn-send-code-chat'),
    btnExecuteBlenderScript: document.getElementById('btn-execute-blender-script'),
    btnQaBlenderCode: document.getElementById('btn-qa-blender-code'),

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
      btn_tools_title: 'Open Tools Inspector & Registered Tools',
      modal_tools_title: 'Registered Tools & Integrations',
      modal_tools_desc: 'Overview of registered tools dynamically provided to the assistant. 3D & Blender tools automatically activate when Blender is connected or 3D Workspace is open.',
      btn_enable_all_tools: 'Enable All',
      btn_disable_all_tools: 'Disable All',
      btn_reset_tools: 'Reset Defaults',
      category_3d: '3D & Blender',
      category_web: 'Web & Research',
      category_system: 'System & Vision',
      tool_status_active: 'Active',
      tool_status_context_off: 'Context Off',
      tool_status_disabled: 'Disabled',
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
      tool_running: 'Running tool',
      tool_finished: 'Completed',
      prompt_placeholder: 'Type a query or Blender command... (Enter to send, Shift+Enter for newline)',
      attach_file_title: 'Attach document for RAG (PDF, TXT, DOCX)',
      mic_btn_title: 'Voice recording (Whisper STT)',
      proofread_btn_title: 'Proofread text (AI)',
      proofread_empty_hint: 'Please write or paste text to proofread first.',
      apply_to_input: 'Use in input',
      applied_to_input: 'Applied!',
      apply_to_input_title: 'Insert corrected text into the input field',
      prompt_shortcut_hint: 'Enter to send • Shift+Enter for new line',
      send_btn_title: 'Send message',
      stop_btn_title: 'Stop generation',
      default_doc_prompt: 'Process this attached document.',

      resizer_title_right: 'Drag to resize right sidebar',
      inspector_title: '3D VIEWPORT & TELEMETRY',
      btn_refresh_telemetry_title: 'Refresh snapshot and metrics',
      tab_3d: '3D Workspace',
      tab_3d_title: '3D Workspace (Blender Viewport & Commands)',
      tab_research: 'Research',
      tab_research_title: 'Web Research & Knowledge Base References',
      tab_agent: 'Agent Log',
      tab_agent_title: 'Agent Execution Workflow & Tool Traces',
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
      qa_offline_banner: 'Blender is offline. Commands will pre-fill into chat prompt. Connect Blender to run directly.',
      qa_offline_warning: 'Blender is offline. Commands will prefill prompt.',
      qa_offline_toast: 'Blender is offline. Start the receiver script (blender_receiver.py) in Blender to execute directly.',
      qa_group_cad: '1. Geometry & Parametric CAD',
      qa_group_mesh: '2. Topology & 3D Print Audit (Mesh Doctor)',
      qa_group_materials: '3. Materials, UV & Textures',
      qa_group_scene: '4. Scene, Studio & Compositor',
      qa_group_animation: '5. Rigging & Animation',
      qa_group_executor: '6. Direct Code Execution',

      qa_cad_model_title: 'Parametric Model',
      qa_cad_model_desc: 'Generate a parametric 3D model with following dimensions (generate_parametric_model)',
      qa_modifiers_title: 'Apply Modifiers',
      qa_modifier_stack_title: 'Apply Modifiers',
      qa_modifiers_desc: 'Apply and optimize modifier stack on the selected object (apply_modifier_stack)',
      qa_modifier_stack_desc: 'Apply and optimize modifier stack on the selected object (apply_modifier_stack)',
      qa_geonodes_title: 'Geometry Nodes Bridge',
      qa_geonodes_desc: 'Create a procedural Geometry Nodes setup (create_geometry_nodes_bridge)',
      qa_vectorize_title: 'Vector to 3D',
      qa_vectorize_desc: 'Convert vector curve or SVG image into extruded 3D geometry (vectorize_image_to_3d)',
      qa_aimesh_title: 'TripoSR AI Mesh',
      qa_ai_mesh_title: 'TripoSR AI Mesh',
      qa_aimesh_desc: 'Generate conceptual 3D mesh from input image via TripoSR AI (generate_local_ai_mesh)',
      qa_ai_mesh_desc: 'Generate conceptual 3D mesh from input image via TripoSR AI (generate_local_ai_mesh)',

      qa_mesh_audit_title: 'Audit Mesh Topology',
      qa_mesh_audit_desc: 'Immediate audit of non-manifold geometry, wall thickness and holes for slicer (mesh_doctor_audit)',
      qa_mesh_repair_title: 'Repair Mesh',
      qa_mesh_repair_desc: 'Repair defective topology, cap holes and clean mesh for 3D print (mesh_doctor_repair)',
      qa_inspect_scene_title: 'Inspect Scene',
      qa_inspect_scene_desc: 'Immediate overview of objects, hierarchy, dimensions and polygon counts (inspect_blender_scene)',

      qa_shader_title: 'Procedural PBR Shader',
      qa_shader_desc: 'Create procedural PBR material node tree including Principled BSDF (create_procedural_shader)',
      qa_texel_audit_title: 'Texel Density Audit',
      qa_texel_audit_desc: 'Immediate measurement and report of texel density across selected models (uv_texel_audit)',
      qa_smart_uv_title: 'Smart UV Pack',
      qa_smart_uv_desc: 'Perform smart UV unwrap and optimal island packing with margin (smart_uv_pack)',

      qa_studio_title: 'Product Photo Studio',
      qa_studio_desc: 'Create product photo studio with backdrop, camera and 3-point lighting (create_product_studio)',
      qa_blueprint_title: 'Blueprint References',
      qa_blueprint_desc: 'Set up blueprint reference planes in orthographic views (setup_blueprint_reference)',
      qa_compositor_title: 'Compositor Setup',
      qa_compositor_desc: 'Set up render compositor passes including denoiser node (setup_compositor)',

      qa_autorig_title: 'Auto-Rig & Skinning',
      qa_autorig_desc: 'Apply auto-rig (ARMATURE_AUTO) and vertex skinning to active mesh (auto_rig_and_skin)',
      qa_fcurve_title: 'F-Curves & Interpolation',
      qa_fcurve_desc: 'Apply animation keyframes and smooth F-curves (apply_fcurve_animation)',
      qa_motion_nodes_title: 'Motion Nodes Setup',
      qa_motion_nodes_desc: 'Configure procedural motion nodes and kinematic constraints (create_motion_node_setup)',

      qa_blender_code_title: 'Run Python in Blender',
      qa_blender_code_desc: 'Open editor dialog to directly send and execute Python code in Blender (execute_blender_code)',
      modal_blender_code_title: 'Execute Python Code in Blender',
      modal_blender_code_desc: 'Directly execute Python / bpy code in the running Blender session via TCP socket (port 9876).',
      blender_code_output_header: 'Blender Execution Output:',
      btn_send_code_chat: 'Ask AI with this Script',
      btn_execute_blender_script: 'Execute in Blender',
      blender_code_empty: 'Please enter Python code to execute.',
      blender_code_running: 'Executing in Blender...',
      blender_code_success: 'Script executed successfully.',
      blender_code_error: 'Blender execution error: ',

      card_web_research_title: 'LIVE WEB RESEARCH & SOURCES',
      no_web_research: 'No web research queries in this session.',
      card_rag_context_title: 'SEMANTIC MEMORY (RAG) CHUNKS',
      no_rag_context: 'No semantic memory queries performed yet.',
      btn_open_knowledge_modal: 'Open Knowledge Base',
      card_agent_steps_title: 'AGENT WORKFLOW & TOOL TRACES',
      no_agent_steps: 'Waiting for agent actions...',
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
      sources_count: '{count} sources',
      chunks_count: '{count} chunks',
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
      btn_tools_title: 'Otevřít inspektor nástrojů a registrace',
      modal_tools_title: 'Inspektor nástrojů & Registrace',
      modal_tools_desc: 'Přehled registrovaných nástrojů předávaných modelu do systémového promptu. 3D nástroje se dynamicky aktivují pouze při dostupném Blenderu nebo v 3D režimu.',
      btn_enable_all_tools: 'Povolit vše',
      btn_disable_all_tools: 'Zakázat vše',
      btn_reset_tools: 'Výchozí',
      category_3d: '3D & Blender',
      category_web: 'Web & Rešerše',
      category_system: 'Systém & Vision',
      tool_status_active: 'Aktivní',
      tool_status_context_off: 'Kontextově vypnuto',
      tool_status_disabled: 'Vypnuto',
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
      tool_running: 'Spouštím nástroj',
      tool_finished: 'Dokončeno',
      prompt_placeholder: 'Napište dotaz nebo příkaz pro Blender... (Enter pro odeslání, Shift+Enter pro nový řádek)',
      attach_file_title: 'Připojit dokument pro RAG (PDF, TXT, DOCX)',
      mic_btn_title: 'Hlasový záznam (přepis přes Whisper)',
      proofread_btn_title: 'Zkontrolovat pravopis a stylistiku (AI)',
      proofread_empty_hint: 'Nejprve napište nebo vložte text ke korektuře.',
      apply_to_input: 'Použít ve vstupu',
      applied_to_input: 'Vloženo!',
      apply_to_input_title: 'Vložit opravený text zpět do vstupního pole',
      prompt_shortcut_hint: 'Enter pro odeslání • Shift+Enter pro nový řádek',
      send_btn_title: 'Odeslat zprávu',
      stop_btn_title: 'Zastavit generování',
      default_doc_prompt: 'Zpracuj tento přiložený dokument.',

      resizer_title_right: 'Tažením změnit šířku pravého panelu',
      inspector_title: '3D VIEWPORT & TELEMETRIE',
      btn_refresh_telemetry_title: 'Obnovit snímek a metriky',
      tab_3d: '3D Workspace',
      tab_3d_title: '3D Pracovní plocha (Blender Viewport & Příkazy)',
      tab_research: 'Rešerše',
      tab_research_title: 'Webové rešerše a citace z báze znalostí',
      tab_agent: 'Agent Log',
      tab_agent_title: 'Kroky agenta a volání nástrojů',
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
      qa_offline_banner: 'Blender je offline. Příkazy se předvyplní do chatu. Pro přímé provedení spusťte skript v Blenderu.',
      qa_offline_warning: 'Blender je offline. Příkazy předvyplní prompt.',
      qa_offline_toast: 'Blender je offline. Pro přímé provedení spusťte skript (blender_receiver.py) v Blenderu.',
      qa_group_cad: '1. Geometrie a parametrické CAD modelování',
      qa_group_mesh: '2. Topologie a příprava na 3D tisk (Mesh Doctor)',
      qa_group_materials: '3. Materiály, UV a textury',
      qa_group_scene: '4. Scéna, studio a kompozitor',
      qa_group_animation: '5. Rigging a Animace',
      qa_group_executor: '6. Přímý exekutor',

      qa_cad_model_title: 'Parametrický model',
      qa_cad_model_desc: 'Vygenerování parametrického 3D modelu dílu dle rozměrů (generate_parametric_model)',
      qa_modifiers_title: 'Aplikovat modifikátory',
      qa_modifier_stack_title: 'Aplikovat modifikátory',
      qa_modifiers_desc: 'Aplikace a optimalizace zásobníku modifikátorů na vybraném objektu (apply_modifier_stack)',
      qa_modifier_stack_desc: 'Aplikace a optimalizace zásobníku modifikátorů na vybraném objektu (apply_modifier_stack)',
      qa_geonodes_title: 'Geometry Nodes můstek',
      qa_geonodes_desc: 'Vytvoření procedurálního Geometry Nodes setupu (create_geometry_nodes_bridge)',
      qa_vectorize_title: 'Vektor do 3D',
      qa_vectorize_desc: 'Převedení vektorového nákresu či SVG na vysunutou 3D geometrii (vectorize_image_to_3d)',
      qa_aimesh_title: 'TripoSR AI Mesh',
      qa_ai_mesh_title: 'TripoSR AI Mesh',
      qa_aimesh_desc: 'Vygenerování konceptuálního 3D meshe z podkladového obrázku přes TripoSR AI (generate_local_ai_mesh)',
      qa_ai_mesh_desc: 'Vygenerování konceptuálního 3D meshe z podkladového obrázku přes TripoSR AI (generate_local_ai_mesh)',

      qa_mesh_audit_title: 'Audit topologie & stěn',
      qa_mesh_audit_desc: 'Okamžité spuštění auditu non-manifold geometrie, tloušťky stěn a děr pro slicer (mesh_doctor_audit)',
      qa_mesh_repair_title: 'Oprava meshe',
      qa_mesh_repair_desc: 'Oprava vadné topologie, zacelení děr a vyčištění meshe pro 3D tisk (mesh_doctor_repair)',
      qa_inspect_scene_title: 'Inspekce scény',
      qa_inspect_scene_desc: 'Okamžitý přehled objektů, hierarchie, rozměrů a počtu polygonů (inspect_blender_scene)',

      qa_shader_title: 'Procedurální PBR shader',
      qa_shader_desc: 'Vytvoření procedurálního PBR materiálu včetně Principled BSDF nodů (create_procedural_shader)',
      qa_texel_audit_title: 'Audit hustoty texelů',
      qa_texel_audit_desc: 'Okamžité přeměření a report hustoty texelů napříč vybranými modely (uv_texel_audit)',
      qa_smart_uv_title: 'Smart UV Pack',
      qa_smart_uv_desc: 'Chytré UV rozbalení a optimální uspořádání ostrovů s mezerami (smart_uv_pack)',

      qa_studio_title: 'Produktové studio',
      qa_studio_desc: 'Vytvoření produktového studia s nekonečným pozadím, kamerou a 3bodovým světlem (create_product_studio)',
      qa_blueprint_title: 'Technické výkresy',
      qa_blueprint_desc: 'Umístění referenčních technických výkresů do ortografických pohledů (setup_blueprint_reference)',
      qa_compositor_title: 'Postprodukce & Kompozitor',
      qa_compositor_desc: 'Nastavení kompozitoru pro finální render včetně denoise nodu (setup_compositor)',

      qa_autorig_title: 'Auto-Rig & Skinning',
      qa_autorig_desc: 'Aplikace automatického auto-rigu (ARMATURE_AUTO) a skinningu na aktivní mesh (auto_rig_and_skin)',
      qa_fcurve_title: 'Animační křivky (F-Curves)',
      qa_fcurve_desc: 'Aplikace animace a vyhlazení F-křivek pro pohyb či rotaci (apply_fcurve_animation)',
      qa_motion_nodes_title: 'Motion Nodes Setup',
      qa_motion_nodes_desc: 'Nastavení procedurálních vazeb a pohybových nodů pro dynamiku (create_motion_node_setup)',

      qa_blender_code_title: 'Spustit Python skript',
      qa_blender_code_desc: 'Otevře editor nebo dialog pro přímé zadání Python skriptu do Blender API (execute_blender_code)',
      modal_blender_code_title: 'Spustit Python kód v Blenderu',
      modal_blender_code_desc: 'Přímé spuštění Python / bpy kódu v běžícím Blenderu přes TCP socket (port 9876).',
      blender_code_output_header: 'Výstup z Blenderu:',
      btn_send_code_chat: 'Vložit do chatu s dotazem',
      btn_execute_blender_script: 'Spustit v Blenderu',
      blender_code_empty: 'Zadejte prosím Python kód ke spuštění.',
      blender_code_running: 'Spouštím v Blenderu...',
      blender_code_success: 'Skript byl úspěšně vykonán.',
      blender_code_error: 'Chyba při spuštění v Blenderu: ',

      card_web_research_title: 'WEBOVÉ REŠERŠE & ZDROJE',
      no_web_research: 'V této relaci zatím neproběhlo webové vyhledávání.',
      card_rag_context_title: 'ÚRYVKY ZE SÉMANTICKÉ PAMĚTI (RAG)',
      no_rag_context: 'Zatím nebyly načteny žádné bloky ze znalostní báze.',
      btn_open_knowledge_modal: 'Otevřít bázi znalostí',
      card_agent_steps_title: 'PRŮBĚH AGENTA & VOLÁNÍ NÁSTROJŮ',
      no_agent_steps: 'Čekám na akce agenta...',
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
      sources_count: '{count} zdrojů',
      chunks_count: '{count} úseků',
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

  const QA_PREFILL_PROMPTS = {
    en: {
      'btn-qa-cad-model': 'Generate a parametric 3D model with following dimensions: ',
      'btn-qa-modifier-stack': 'Apply and optimize modifier stack on the selected object.',
      'btn-qa-geonodes': 'Create a procedural Geometry Nodes setup for: ',
      'btn-qa-vectorize': 'Convert vector curve/image into extruded 3D geometry.',
      'btn-qa-ai-mesh': 'Generate conceptual 3D mesh from input image.',
      'btn-qa-mesh-audit': 'Audit mesh topology and wall thickness for 3D printing (non-manifold geometry, holes for slicer).',
      'btn-qa-mesh-repair': 'Repair defective topology, cap holes and clean mesh for 3D print.',
      'btn-qa-inspect-scene': 'Inspect scene in Blender and report object hierarchy, dimensions, and polygon counts.',
      'btn-qa-shader': 'Create procedural PBR material (type, color, roughness): ',
      'btn-qa-texel-audit': 'Measure and report texel density across selected models.',
      'btn-qa-smart-uv': 'Perform smart UV unwrap and optimal island packing with margin: ',
      'btn-qa-studio': 'Create product photo studio with backdrop, camera and 3-point lighting.',
      'btn-qa-blueprint': 'Set up blueprint reference planes in orthographic views.',
      'btn-qa-compositor': 'Set up render compositor passes including denoiser.',
      'btn-qa-autorig': 'Apply auto-rig (ARMATURE_AUTO) and vertex skinning to active mesh.',
      'btn-qa-fcurve': 'Apply animation keyframes and smooth F-curves for: ',
      'btn-qa-motion-nodes': 'Configure procedural motion nodes and constraints for: ',
    },
    cs: {
      'btn-qa-cad-model': 'Vygeneruj parametrický 3D model dílu s těmito rozměry: ',
      'btn-qa-modifier-stack': 'Aplikuj a optimalizuj zásobník modifikátorů na vybraném objektu.',
      'btn-qa-geonodes': 'Vytvoř procedurální Geometry Nodes setup pro: ',
      'btn-qa-vectorize': 'Převeď vektorový nákres na vysunutou 3D geometrii.',
      'btn-qa-ai-mesh': 'Vygeneruj konceptuální 3D mesh z podkladového obrázku.',
      'btn-qa-mesh-audit': 'Proveď audit topologie a stěn meshe pro 3D tisk (non-manifold hrany, díry pro slicer).',
      'btn-qa-mesh-repair': 'Oprav vadnou topologii, zacel díry a vyčisti mesh pro 3D tisk.',
      'btn-qa-inspect-scene': 'Prozkoumej scénu v Blenderu a vypiš přehled objektů, hierarchii, rozměry a počet polygonů.',
      'btn-qa-shader': 'Vytvoř procedurální PBR materiál (typ, barva, drsnost): ',
      'btn-qa-texel-audit': 'Přeměř a vypiš report hustoty texelů (Texel Density) napříč vybranými modely.',
      'btn-qa-smart-uv': 'Proveď chytré UV rozbalení a optimální uspořádání ostrovů s mezerami: ',
      'btn-qa-studio': 'Vytvoř produktové studio s nekonečným pozadím, kamerou a 3bodovým světlem.',
      'btn-qa-blueprint': 'Umísti referenční technické výkresy do ortografických pohledů (přední, boční, horní).',
      'btn-qa-compositor': 'Nastav kompozitor pro finální render včetně denoise nodu.',
      'btn-qa-autorig': 'Aplikuj automatický auto-rig (ARMATURE_AUTO) a skinning na aktivní mesh.',
      'btn-qa-fcurve': 'Aplikuj animaci a vyhlaď F-křivky pro: ',
      'btn-qa-motion-nodes': 'Nastav procedurální vazby a pohybové nody pro: ',
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

    // Nativní kontrola pravopisu - dynamická aktualizace atributů lang a spellcheck
    if (el.promptInput) {
      el.promptInput.setAttribute('lang', lang);
      el.promptInput.setAttribute('spellcheck', 'true');
    }

    // Dynamicky renderovaná akční tlačítka v kartách zpráv
    document.querySelectorAll('.apply-to-input-btn').forEach(btn => {
      btn.setAttribute('title', t('apply_to_input_title'));
      const span = btn.querySelector('span');
      if (span && !btn.classList.contains('applied')) {
        span.textContent = t('apply_to_input');
      }
    });
  }

  function setLanguage(lang) {
    if (lang !== 'en' && lang !== 'cs') lang = 'en';
    state.language = lang;
    try {
      localStorage.setItem('polygon_language', lang);
    } catch (e) {}

    // Dynamická aktualizace jazyka a slovníku pro nativní spellcheck
    if (el.promptInput) {
      el.promptInput.setAttribute('lang', lang);
      el.promptInput.setAttribute('spellcheck', 'true');
    }

    applyTranslations(lang);
    renderSessionsList();
    updateActiveToolsBadge();
    if (el.modalTools && el.modalTools.style.display !== 'none') {
      renderToolsInspector();
    }
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

  function switchInspectorTab(tabName, savePref = true) {
    const validTabs = ['3d', 'research', 'agent'];
    const active = validTabs.includes(tabName) ? tabName : '3d';
    state.activeRightTab = active;

    const tabBtns = {
      '3d': el.tabBtn3d,
      'research': el.tabBtnResearch,
      'agent': el.tabBtnAgent,
    };
    const tabPanes = {
      '3d': el.pane3d,
      'research': el.paneResearch,
      'agent': el.paneAgent,
    };

    Object.keys(tabBtns).forEach(key => {
      const btn = tabBtns[key];
      const pane = tabPanes[key];
      const isTarget = key === active;
      if (btn) btn.classList.toggle('active', isTarget);
      if (pane) {
        pane.classList.toggle('active', isTarget);
        pane.style.display = isTarget ? 'flex' : 'none';
      }
    });

    if (savePref) {
      try {
        localStorage.setItem('polygon_active_right_tab', active);
      } catch (e) {}
    }

    updateActiveToolsBadge();
    if (el.modalTools && el.modalTools.style.display !== 'none') {
      renderToolsInspector();
    }
  }

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

      // 6. Active Inspector tab (3d, research, agent)
      const storedTab = localStorage.getItem('polygon_active_right_tab') || '3d';
      switchInspectorTab(storedTab, false);

      // 7. Tools Inspector manual toggles configuration
      const storedTools = localStorage.getItem('polygon_tools_config');
      if (storedTools) {
        try {
          state.toolsConfig = JSON.parse(storedTools) || {};
        } catch (e) {
          state.toolsConfig = {};
        }
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
      let minCardHeight = 110;

      const onPointerMove = (e) => {
        if (!isDragging) return;
        const deltaY = e.clientY - startY;
        const newHeight = Math.max(minCardHeight, Math.min(startHeight + deltaY, 900));
        targetCard.style.height = `${newHeight}px`;
        targetCard.style.flex = '0 0 auto';
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
        const compMin = parseInt(window.getComputedStyle(targetCard).minHeight, 10);
        minCardHeight = (!isNaN(compMin) && compMin > 0) ? compMin : 110;
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
      localStorage.removeItem('polygon_active_right_tab');

      state.language = 'en';
      state.leftSidebarWidth = '280px';
      state.rightSidebarWidth = '340px';
      state.onlineMode = true;
      state.ragEnabled = true;
      state.ttsEnabled = false;
      state.selectedPreset = 'standard';
      state.activeRightTab = '3d';

      document.documentElement.style.setProperty('--left-sidebar-width', '280px');
      document.documentElement.style.setProperty('--right-sidebar-width', '340px');
      document.querySelectorAll('.inspector-card[id]').forEach(card => {
        card.style.height = '';
      });

      localStorage.removeItem('polygon_tools_config');
      state.toolsConfig = {};

      if (el.toggleOnline) el.toggleOnline.classList.add('active');
      if (el.toggleRag) el.toggleRag.classList.add('active');
      if (el.toggleTts) el.toggleTts.classList.remove('active');
      if (el.selectPreset) el.selectPreset.value = 'standard';

      if (el.cfgTemp) el.cfgTemp.value = 0.7;
      if (el.cfgTokens) el.cfgTokens.value = 1024;
      if (el.cfgSysprompt) el.cfgSysprompt.value = '';
      if (el.cfgLanguage) el.cfgLanguage.value = 'en';

      switchInspectorTab('3d', false);
      setLanguage('en');
      updateActiveToolsBadge();
      closeSettingsModal();
      logConsole('Factory reset complete. Defaults restored (EN).', 'info');
    } catch (err) {
      logConsole(`Reset error: ${err.message}`, 'error');
    }
  }

  // ===========================================================================
  // TOOLS INSPECTOR & CONTEXTUAL FILTERING
  // ===========================================================================
  function isStandardPreset(preset) {
    if (!preset) return false;
    const p = String(preset).trim().toLowerCase();
    return p === 'standard' || p.includes('standard') || p === 'none' || p === 'null' || p === 'vypnuto (standardní chat)' || p === 'standard assistant (off)';
  }

  function isToolEffectiveActive(toolName) {
    if (state.toolsConfig[toolName] === false) return false;

    const tool = state.toolsRegistry.find(t => t.name === toolName);
    const cat = tool ? tool.category : 'system';

    if (cat === 'web') {
      if (toolName === 'search_web' && !state.onlineMode) return false;
      if ((toolName === 'query_local_rag' || toolName === 'query_memory_rag') && !state.ragEnabled) return false;
      return true;
    }

    if (cat === '3d') {
      if (isStandardPreset(state.selectedPreset)) return false;
      const is3dAllowed = Boolean(state.blenderConnected) || (state.activeRightTab === '3d');
      return is3dAllowed;
    }

    return true;
  }

  function getEffectiveActiveToolNames() {
    return state.toolsRegistry
      .filter(t => isToolEffectiveActive(t.name))
      .map(t => t.name);
  }

  function updateActiveToolsBadge() {
    const activeList = getEffectiveActiveToolNames();
    const count = activeList.length;
    const total = state.toolsRegistry.length;
    const isCs = (state.language === 'cs');

    let text = '';
    if (isCs) {
      if (count === 1) text = '1 Nástroj aktivní';
      else if (count >= 2 && count <= 4) text = `${count} Nástroje aktivní`;
      else text = `${count} Nástrojů aktivních`;
    } else {
      text = (count === 1) ? '1 Tool Active' : `${count} Tools Active`;
    }

    if (el.toolsCountText) {
      el.toolsCountText.textContent = text;
    }
    const modalBadge = document.getElementById('modal-active-tools-count');
    if (modalBadge) {
      modalBadge.textContent = isCs ? `${count} / ${total} Aktivních` : `${count} / ${total} Active`;
    }
  }

  function openToolsModal() {
    renderToolsInspector();
    if (el.modalTools) {
      el.modalTools.style.display = 'flex';
    }
  }

  function closeToolsModal() {
    if (el.modalTools) {
      el.modalTools.style.display = 'none';
    }
  }

  function renderToolsInspector() {
    const container = document.getElementById('tools-categories-container');
    if (!container) return;

    const isCs = (state.language === 'cs');
    updateActiveToolsBadge();

    const categories = [
      {
        id: '3d',
        name: isCs ? '3D & Blender' : '3D & Blender',
        icon: '<path d="m21.12 6.4-6.05-4.06a2 2 0 0 0-2.17-.05L2.95 8.41a2 2 0 0 0-.95 1.7v8.58a2 2 0 0 0 1.05 1.76l6.05 4.07a2 2 0 0 0 2.16.05l9.89-6.12a2 2 0 0 0 .95-1.7V9.17a2 2 0 0 0-1-.77ZM12 4.14l7.63 5.12L12 14.36 4.37 9.26 12 4.14Z"></path>',
        statusInfo: isCs
          ? (state.blenderConnected ? '✓ Blender připojen' : (state.activeRightTab === '3d' ? '⚡ 3D Režim aktivní' : '⚠️ Offline (v klidu neaktivní)'))
          : (state.blenderConnected ? '✓ Blender online' : (state.activeRightTab === '3d' ? '⚡ 3D Tab active' : '⚠️ Offline (inactive in idle)')),
      },
      {
        id: 'web',
        name: isCs ? 'Web & Rešerše' : 'Web & Research',
        icon: '<circle cx="12" cy="12" r="10"></circle><line x1="2" x2="22" y1="12" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>',
        statusInfo: isCs
          ? `${state.onlineMode ? '✓ Web zapnut' : '✕ Web vypnut'} • ${state.ragEnabled ? '✓ RAG zapnut' : '✕ RAG vypnut'}`
          : `${state.onlineMode ? '✓ Web on' : '✕ Web off'} • ${state.ragEnabled ? '✓ RAG on' : '✕ RAG off'}`,
      },
      {
        id: 'system',
        name: isCs ? 'Systém' : 'System',
        icon: '<rect width="20" height="14" x="2" y="3" rx="2"></rect><line x1="8" x2="16" y1="21" y2="21"></line><line x1="12" x2="12" y1="17" y2="21"></line>',
        statusInfo: isCs ? '✓ Připraveno' : '✓ Ready',
      },
    ];

    let html = '';
    categories.forEach(cat => {
      const toolsInCat = state.toolsRegistry.filter(t => t.category === cat.id);
      const activeInCat = toolsInCat.filter(t => isToolEffectiveActive(t.name)).length;

      html += `
        <div class="tool-category-group" data-category="${cat.id}">
          <div class="tool-category-header">
            <div class="tool-category-title-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${cat.icon}</svg>
              <span>${escapeHtml(cat.name)}</span>
              <span class="tool-category-status-note" style="font-size: 11px; font-weight: normal; color: var(--text-secondary); margin-left: 8px;">(${escapeHtml(cat.statusInfo)})</span>
            </div>
            <span class="tool-category-badge">${activeInCat} / ${toolsInCat.length}</span>
          </div>
          <div class="tool-category-items">
      `;

      toolsInCat.forEach(tool => {
        const isManualEnabled = (state.toolsConfig[tool.name] !== false);
        const isEffective = isToolEffectiveActive(tool.name);
        const title = isCs ? tool.title_cs : tool.title_en;
        const desc = isCs ? tool.desc_cs : tool.desc_en;

        let pillClass = 'active';
        let pillText = isCs ? 'Aktivní' : 'Active';
        if (!isManualEnabled) {
          pillClass = 'manual-disabled';
          pillText = isCs ? 'Vypnuto' : 'Disabled';
        } else if (!isEffective) {
          pillClass = 'context-disabled';
          pillText = isCs ? 'Kontextově vypnuto' : 'Context Off';
        }

        html += `
          <div class="tool-item-card" data-tool="${tool.name}">
            <div class="tool-item-info">
              <div class="tool-item-header">
                <span class="tool-item-title">${escapeHtml(title)}</span>
                <code class="tool-item-name">${tool.name}()</code>
                <span class="tool-status-pill ${pillClass}">${pillText}</span>
              </div>
              <div class="tool-item-desc">${escapeHtml(desc)}</div>
            </div>
            <label class="tool-switch" title="${isCs ? 'Přepnout aktivaci nástroje' : 'Toggle tool activation'}">
              <input type="checkbox" class="tool-toggle-checkbox" data-tool-name="${tool.name}" ${isManualEnabled ? 'checked' : ''}>
              <span class="tool-slider"></span>
            </label>
          </div>
        `;
      });

      html += `
          </div>
        </div>
      `;
    });

    container.innerHTML = html;

    container.querySelectorAll('.tool-toggle-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const tName = e.target.getAttribute('data-tool-name');
        const val = e.target.checked;
        state.toolsConfig[tName] = val;
        try {
          localStorage.setItem('polygon_tools_config', JSON.stringify(state.toolsConfig));
        } catch (err) {}
        renderToolsInspector();
        updateActiveToolsBadge();
      });
    });
  }

  function setAllToolsEnabled(enableVal) {
    state.toolsRegistry.forEach(t => {
      state.toolsConfig[t.name] = Boolean(enableVal);
    });
    try {
      localStorage.setItem('polygon_tools_config', JSON.stringify(state.toolsConfig));
    } catch (err) {}
    renderToolsInspector();
    updateActiveToolsBadge();
  }

  function resetToolsToDefaults() {
    state.toolsConfig = {};
    try {
      localStorage.removeItem('polygon_tools_config');
    } catch (err) {}
    renderToolsInspector();
    updateActiveToolsBadge();
  }

  // ===========================================================================
  // CONTEXT WORKSPACE FEEDS: RESEARCH & AGENT TRACES
  // ===========================================================================
  const MAX_AGENT_STEPS = 100;

  function addAgentStep(message, type = 'info', badge = 'STEP') {
    if (!el.agentStepsTimeline || !message) return;

    // Remove empty state placeholder if present
    const emptyState = el.agentStepsTimeline.querySelector('.tab-empty-state');
    if (emptyState) emptyState.remove();

    const item = document.createElement('div');
    item.className = `agent-step-item ${type}`;

    const time = new Date().toLocaleTimeString();
    item.innerHTML = `
      <div class="agent-step-header">
        <span class="agent-step-badge">${escapeHtml(badge)}</span>
        <span class="agent-step-time">${time}</span>
      </div>
      <div class="agent-step-body">${escapeHtml(message)}</div>
    `;

    el.agentStepsTimeline.appendChild(item);

    // Keep FIFO limit
    while (el.agentStepsTimeline.children.length > MAX_AGENT_STEPS) {
      el.agentStepsTimeline.removeChild(el.agentStepsTimeline.firstElementChild);
    }

    el.agentStepsTimeline.scrollTop = el.agentStepsTimeline.scrollHeight;
  }

  function clearAgentSteps() {
    if (!el.agentStepsTimeline) return;
    el.agentStepsTimeline.innerHTML = `
      <div class="tab-empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
        <span>${escapeHtml(t('no_agent_steps'))}</span>
      </div>
    `;
  }

  function normalizeWebSearchResults(rawResults) {
    if (!rawResults) return { sources: [], textMessage: '' };

    let current = rawResults;

    // 1. Zda nepřišel JSON string vyžadující JSON.parse()
    if (typeof current === 'string') {
      const trimmed = current.trim();
      if (!trimmed) return { sources: [], textMessage: '' };

      // Pokus o JSON parse, pokud string začíná jako JSON objekt nebo pole
      if ((trimmed.startsWith('[') && trimmed.endsWith(']')) || (trimmed.startsWith('{') && trimmed.endsWith('}'))) {
        try {
          current = JSON.parse(trimmed);
        } catch (e) {
          // Není validní JSON, pokračujeme jako se stringem
        }
      }
    }

    // 2. Kontrola vnořených klíčů (results?.results, results?.sources, results?.data, results?.items)
    if (current && typeof current === 'object' && !Array.isArray(current)) {
      if (Array.isArray(current.results)) {
        current = current.results;
      } else if (Array.isArray(current.sources)) {
        current = current.sources;
      } else if (Array.isArray(current.data)) {
        current = current.data;
      } else if (Array.isArray(current.items)) {
        current = current.items;
      }
    }

    // 3. Pokud je výsledkem pole, namapujeme položky do sjednoceného formátu
    if (Array.isArray(current)) {
      const sources = [];
      for (const item of current) {
        if (!item) continue;
        if (typeof item === 'string') {
          const isUrl = item.startsWith('http://') || item.startsWith('https://');
          sources.push({
            title: isUrl ? item : 'Web Source',
            url: isUrl ? item : '#',
            snippet: isUrl ? '' : item,
          });
        } else if (typeof item === 'object') {
          sources.push({
            title: item.title || item.name || item.url || 'Web Source',
            url: item.url || item.link || '#',
            snippet: item.snippet || item.content || item.description || '',
          });
        }
      }
      return { sources, textMessage: '' };
    }

    // 4. Pokud jde o obyčejný text/string nebo pole nelze sestavit, zpracuj jej jako textovou zprávu
    let textMessage = '';
    if (typeof current === 'string') {
      // Zkusíme najít Markdown odkazy [title](url)
      const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g;
      const extracted = [];
      let match;
      while ((match = linkRegex.exec(current)) !== null) {
        extracted.push({
          title: match[1].trim(),
          url: match[2].trim(),
          snippet: '',
        });
      }
      if (extracted.length > 0) {
        return { sources: extracted, textMessage: '' };
      }
      textMessage = current.trim();
    } else if (current && typeof current === 'object') {
      textMessage = current.result || current.message || current.error || JSON.stringify(current);
    } else {
      textMessage = String(current);
    }

    if (textMessage.length > 300) {
      textMessage = textMessage.slice(0, 297) + '…';
    }

    return { sources: [], textMessage };
  }

  function addWebResearchResult(query, results = []) {
    if (!el.researchSourcesList) return;
    const emptyState = el.researchSourcesList.querySelector('.tab-empty-state');
    if (emptyState) emptyState.remove();

    const { sources, textMessage } = normalizeWebSearchResults(results);

    const item = document.createElement('div');
    item.className = 'research-source-item';

    let linksHtml = '';
    if (sources.length > 0) {
      linksHtml = sources.map(r => `
        <div class="research-source-entry">
          <a class="research-source-link source-link" href="${escapeHtml(r.url || '#')}" target="_blank" rel="noopener noreferrer">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
            <span>${escapeHtml(r.title || r.url || 'Web Source')}</span>
          </a>
          ${r.snippet ? `<div class="research-source-snippet">${escapeHtml(r.snippet)}</div>` : ''}
        </div>
      `).join('');
    } else if (textMessage) {
      linksHtml = `<div class="research-source-snippet source-text-message">${escapeHtml(textMessage)}</div>`;
    }

    item.innerHTML = `
      <div class="source-query"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> ${escapeHtml(query)}</div>
      <div class="source-links">${linksHtml}</div>
    `;

    el.researchSourcesList.prepend(item);

    const totalSources = el.researchSourcesList.querySelectorAll('.research-source-item').length;
    if (el.badgeResearchCount) {
      el.badgeResearchCount.textContent = t('sources_count', { count: totalSources });
    }
  }

  function addRagSnippet(docTitle, snippetText, score = null) {
    if (!el.ragSnippetsList) return;
    const emptyState = el.ragSnippetsList.querySelector('.tab-empty-state');
    if (emptyState) emptyState.remove();

    const item = document.createElement('div');
    item.className = 'rag-snippet-item';

    const scoreTag = score !== null ? `<span class="snippet-score">${Math.round(score * 100)}% match</span>` : '';

    item.innerHTML = `
      <div class="snippet-header">
        <span class="snippet-doc-name"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline></svg> ${escapeHtml(docTitle || 'Document Chunk')}</span>
        ${scoreTag}
      </div>
      <div class="snippet-body">${escapeHtml(snippetText)}</div>
    `;

    el.ragSnippetsList.prepend(item);

    const totalSnippets = el.ragSnippetsList.querySelectorAll('.rag-snippet-item').length;
    if (el.badgeRagCount) {
      el.badgeRagCount.textContent = t('chunks_count', { count: totalSnippets });
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
      const card = appendMessageCard(msg.role, msg.content, false);
      if (msg.role === 'assistant') {
        updateMessageActions(card, msg.content, false);
      }
    });

    scrollToBottom();
  }

  function appendMessageCard(role, initialContent = '', isLive = false) {
    if (el.welcomeHero) {
      el.welcomeHero.style.display = 'none';
    }

    const card = document.createElement('div');
    card.className = `message-card ${role} ${role === 'user' ? 'user-card' : 'assistant-card'}`;

    const isUser = role === 'user';
    const avatarLetter = isUser ? 'U' : 'A';
    const authorName = isUser ? t('you') : 'Polygon Beater Core';

    card.innerHTML = `
      <div class="message-card-header message-meta">
        <div class="message-avatar">${avatarLetter}</div>
        <span class="message-author message-sender">${escapeHtml(authorName)}</span>
        <span class="message-timestamp">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="message-tool-status-area" style="display: none;"></div>
      <div class="message-body message-content">${isUser ? escapeHtml(initialContent) : renderMarkdown(initialContent)}</div>
      <div class="message-actions-footer" style="display: none;"></div>
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
  // AI PROOFREADING & SPELLCHECK ACTION
  // ===========================================================================
  function showPromptHint(msg) {
    let hint = document.getElementById('prompt-hint-toast');
    if (!hint) {
      hint = document.createElement('div');
      hint.id = 'prompt-hint-toast';
      hint.className = 'prompt-hint-toast';
      const box = document.querySelector('.prompt-box');
      if (box) box.appendChild(hint);
    }
    hint.textContent = msg;
    hint.classList.add('show');
    clearTimeout(hint._timer);
    hint._timer = setTimeout(() => {
      hint.classList.remove('show');
    }, 2800);
  }

  function showToast(msg, type = 'info') {
    let toast = document.getElementById('global-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'global-toast';
      document.body.appendChild(toast);
    }
    toast.className = `global-toast ${type}`;
    toast.textContent = msg;
    void toast.offsetWidth;
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      toast.classList.remove('show');
    }, 3800);
  }

  function extractCorrectedText(text) {
    if (!text || typeof text !== 'string') return null;

    // 1. Heading-based extraction (### Opravený text / ### Corrected Text)
    const headerRegex = /(?:###|\*\*|##|#)\s*(?:Opravený text|Opravená verze(?:\s+textu)?|Corrected Text|Proofread Text)[:*]*\s*\n+([\s\S]*?)(?=(?:\n+(?:###|\*\*|##|#)\s*(?:Přehled úprav|Přehled změn|Provedené úpravy|Provedené změny|Seznam úprav|Úpravy|Změny|Summary of Changes|Changes Made|Changes|Summary)|(?:\n+---)|$))/i;
    const match = text.match(headerRegex);
    let result = null;
    if (match && match[1]) {
      result = match[1].trim();
    }

    // 2. Fallback to text before bullet points if structure has summary
    if (!result) {
      const bulletSplit = text.split(/\n+\s*[-*•]\s+/);
      if (bulletSplit.length > 1 && bulletSplit[0].trim().length > 8) {
        const candidate = bulletSplit[0].replace(/^(?:Zde je opravený text|Here is the corrected text|Opravená verze|Corrected text)[:\s]*/i, '').trim();
        if (candidate.length > 3) {
          result = candidate;
        }
      }
    }

    if (result) {
      // Strip blockquotes (> quote)
      result = result.replace(/^>+\s*/gm, '').trim();
      // Strip outer enclosing quotes
      if ((result.startsWith('"') && result.endsWith('"')) || (result.startsWith('“') && result.endsWith('”'))) {
        result = result.slice(1, -1).trim();
      }
      // Strip code fence blocks if enclosed
      if (result.startsWith('```') && result.endsWith('```')) {
        result = result.replace(/^```[a-z]*\n([\s\S]*?)\n```$/i, '$1').trim();
      }
    }

    return result || null;
  }

  function setPromptInputAndFocus(text) {
    if (!el.promptInput || !text) return;
    el.promptInput.value = text;
    el.promptInput.focus();
    el.promptInput.selectionStart = el.promptInput.selectionEnd = el.promptInput.value.length;
    el.promptInput.style.height = 'auto';
    el.promptInput.style.height = Math.min(el.promptInput.scrollHeight, 180) + 'px';

    const box = document.querySelector('.prompt-box');
    if (box) {
      box.classList.remove('input-applied-highlight');
      void box.offsetWidth;
      box.classList.add('input-applied-highlight');
      setTimeout(() => box.classList.remove('input-applied-highlight'), 850);
    }

    if (el.promptInput.scrollIntoView) {
      el.promptInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function applyTextToInput(text, btn = null) {
    if (!el.promptInput || !text) return;

    el.promptInput.value = text;
    el.promptInput.focus();
    el.promptInput.style.height = 'auto';
    el.promptInput.style.height = Math.min(el.promptInput.scrollHeight, 180) + 'px';

    const box = document.querySelector('.prompt-box');
    if (box) {
      box.classList.remove('input-applied-highlight');
      void box.offsetWidth; // trigger reflow
      box.classList.add('input-applied-highlight');
      setTimeout(() => box.classList.remove('input-applied-highlight'), 850);
    }

    if (btn) {
      const originalHtml = btn.innerHTML;
      btn.classList.add('applied');
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 6 9 17l-5-5"/>
        </svg>
        <span>${escapeHtml(t('applied_to_input'))}</span>
      `;
      setTimeout(() => {
        btn.classList.remove('applied');
        btn.innerHTML = originalHtml;
      }, 1800);
    }

    if (el.promptInput.scrollIntoView) {
      el.promptInput.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function updateMessageActions(card, text, isProofread = false) {
    if (!card) return;
    const actionsFooter = card.querySelector('.message-actions-footer');
    if (!actionsFooter) return;

    const corrected = extractCorrectedText(text);
    if (corrected || isProofread) {
      const textToApply = corrected || text;
      actionsFooter.innerHTML = '';
      actionsFooter.style.display = 'flex';

      const btn = document.createElement('button');
      btn.className = 'message-action-btn apply-to-input-btn';
      btn.setAttribute('title', t('apply_to_input_title'));
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"></path>
          <path d="m15 5 4 4"></path>
        </svg>
        <span>${escapeHtml(t('apply_to_input'))}</span>
      `;
      btn.addEventListener('click', () => {
        applyTextToInput(textToApply, btn);
      });
      actionsFooter.appendChild(btn);
    } else {
      actionsFooter.style.display = 'none';
      actionsFooter.innerHTML = '';
    }
  }

  async function triggerAiProofreading() {
    if (state.isStreaming) return;

    const rawText = el.promptInput ? el.promptInput.value.trim() : '';
    if (!rawText) {
      const hint = t('proofread_empty_hint');
      showPromptHint(hint);
      if (el.promptInput) el.promptInput.focus();
      return;
    }

    const isCs = (state.language === 'cs');
    const instruction = isCs
      ? 'Proveď důkladnou gramatickou, stylistickou a interpunkční korekturu následujícího textu (oprav překlepy, shodu podmětu s přísudkem, čárky a slovosled, se zachováním původního tónu a významu).\n\nOdpověď strukturuj přesně takto:\n### Opravený text\n[Zde uveď pouze čistý opravený text připravený k použití]\n\n### Přehled úprav\n- [stručné odrážky s provedenými změnami]'
      : 'Perform thorough grammatical, stylistic, and punctuation proofreading of the following text (fix typos, subject-verb agreement, commas, and phrasing, preserving original tone and meaning).\n\nStructure your response exactly as follows:\n### Corrected Text\n[Insert only the clean corrected text ready to use]\n\n### Summary of Changes\n- [concise bullet points of changes made]';

    const fullPrompt = `${instruction}\n\nText ke korektuře:\n"${rawText}"`;
    await sendMessage(fullPrompt, { isProofread: true });
  }

  // ===========================================================================
  // CHAT STREAMING (SSE POST /api/chat)
  // ===========================================================================
  async function sendMessage(overridePrompt = null, options = {}) {
    if (state.isStreaming) return;

    const isProofread = Boolean(options && options.isProofread);

    const rawPrompt = (typeof overridePrompt === 'string' && overridePrompt.trim())
      ? overridePrompt.trim()
      : (el.promptInput ? el.promptInput.value.trim() : '');

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
    if (el.promptInput) {
      el.promptInput.value = '';
      el.promptInput.style.height = 'auto';
    }

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
    let reader = null;
    let inactivityTimerId = null;
    let hardLimitTimerId = null;
    state.abortController = new AbortController();

    // 1. Inactivity timeout (90s od posledního přijatého bytu/zprávy/pingu)
    const INACTIVITY_TIMEOUT_MS = 90000;
    const resetWatchdog = () => {
      if (inactivityTimerId) clearTimeout(inactivityTimerId);
      inactivityTimerId = setTimeout(() => {
        if (state.isStreaming) {
          logConsole('Streaming inactivity timeout (90s without bytes/ping). Forcing UI reset.', 'warn');
          if (state.abortController) {
            try {
              state.abortController.abort();
            } catch (e) {}
          }
        }
      }, INACTIVITY_TIMEOUT_MS);
    };
    resetWatchdog();

    // 2. Celkový hard-limit pro web search a těžké CPU úlohy (300 s)
    const TOTAL_HARD_LIMIT_MS = 300000;
    hardLimitTimerId = setTimeout(() => {
      if (state.isStreaming) {
        logConsole('Streaming maximum hard-limit reached (300s). Forcing UI reset.', 'warn');
        if (state.abortController) {
          try {
            state.abortController.abort();
          } catch (e) {}
        }
      }
    }, TOTAL_HARD_LIMIT_MS);

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
        active_tools: getEffectiveActiveToolNames(),
        mode_3d: (state.activeRightTab === '3d'),
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

      try {
        reader = response.body ? response.body.getReader() : null;
      } catch (e) {
        reader = null;
      }
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let isStreamFinished = false;

      while (!isStreamFinished) {
        const { value, done } = await reader.read();
        if (done) break;

        resetWatchdog();
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const payloadStr = trimmed.slice(6).trim();

          // 1. Zpracování koncového signálu [DONE]
          if (payloadStr === '[DONE]' || payloadStr === 'DONE') {
            isStreamFinished = true;
            break;
          }

          let data;
          try {
            data = JSON.parse(payloadStr);
          } catch (e) {
            continue;
          }

          if (data.type === 'ping') {
            // Heartbeat z backendu indikující aktivní výpočet modelu nebo nástroje
            resetWatchdog();
            continue;
          }

          if (data.type === 'session_id') {
            if (data.content && (!state.sessionId || state.sessionId !== data.content)) {
              state.sessionId = data.content;
            }
          } else if (data.type === 'token' || data.type === 'chunk') {
            const tokenText = data.content ?? data.chunk ?? data.text ?? '';
            if (tokenText) {
              fullText += tokenText;
              bodyEl.innerHTML = renderMarkdown(fullText);
              scrollToBottom();
            }
          } else if (data.type === 'tool_start') {
            const toolName = data.tool || data.name || 'tool';
            const statusMsg = `● 🛠️ ${t('tool_running')}: ${toolName}…`;
            if (toolArea) {
              toolArea.style.display = 'block';
              const pill = document.createElement('div');
              pill.className = 'tool-status-pill tool-start-pill';
              pill.textContent = statusMsg;
              toolArea.appendChild(pill);
            }
            if (el.liveStatusText) {
              el.liveStatusText.textContent = statusMsg;
            }
            addAgentStep(`Invoked tool: ${toolName}`, 'info', 'TOOL');
            logConsole(`[Tool Call Start] ${toolName}`, 'info');
            scrollToBottom();
          } else if (data.type === 'tool_end') {
            const toolName = data.tool || data.name || 'tool';
            const doneMsg = `✓ 🛠️ ${toolName} ${t('tool_finished').toLowerCase()}`;
            if (toolArea) {
              toolArea.style.display = 'block';
              const pill = document.createElement('div');
              pill.className = 'tool-status-pill tool-end-pill';
              pill.textContent = doneMsg;
              toolArea.appendChild(pill);
            }
            if (el.liveStatusText) {
              el.liveStatusText.textContent = t('thinking_status');
            }
            addAgentStep(`Completed tool: ${toolName}`, 'info', 'DONE');
            logConsole(`[Tool Call End] ${toolName}`, 'info');
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
            addAgentStep(data.content, 'status', 'TOOL');
            logConsole(data.content, 'info');
            scrollToBottom();
          } else if (data.type === 'agent_step') {
            addAgentStep(data.content, data.step_type || 'info', data.badge || 'STEP');
            logConsole(`[Agent Step] ${data.content}`, 'info');
          } else if (data.type === 'web_search') {
            const rawPayload = (data.sources !== undefined) ? data.sources : data.results;
            addWebResearchResult(data.query || promptText, rawPayload !== undefined ? rawPayload : []);
            addAgentStep(`Web research: "${data.query || promptText}"`, 'info', 'WEB');
          } else if (data.type === 'rag_context') {
            if (Array.isArray(data.snippets)) {
              data.snippets.forEach(s => addRagSnippet(s.doc || s.title, s.text || s.content, s.score));
            } else if (data.content) {
              addRagSnippet(data.doc || 'RAG Memory', data.content, data.score);
            }
            addAgentStep('Retrieved semantic memory chunks from RAG', 'info', 'RAG');
          } else if (data.type === 'methodology') {
            addAgentStep(`Analytical methodology: ${data.content}`, 'methodology', 'FRAMEWORK');
            logConsole(`Methodology: ${data.content}`, 'info');
          } else if (data.type === 'done' || data.type === 'finish' || data.type === 'end') {
            fullText = data.content || fullText;
            bodyEl.innerHTML = renderMarkdown(fullText);
            updateMessageActions(assistantCard, fullText, isProofread);
            scrollToBottom();
            isStreamFinished = true;
            break;
          } else if (data.type === 'error') {
            bodyEl.innerHTML += `<div class="error-badge"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>${escapeHtml(data.content)}</span></div>`;
            addAgentStep(`Error: ${data.content}`, 'error', 'ERROR');
            logConsole(`Error: ${data.content}`, 'error');
            isStreamFinished = true;
            break;
          }
        }
      }

      if (assistantCard && fullText) {
        updateMessageActions(assistantCard, fullText, isProofread);
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
        logConsole('Generation interrupted by user or watchdog.', 'warn');
        bodyEl.innerHTML += `<div class="tool-status-pill abort-pill"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="5" y="5" rx="2"></rect></svg> <span>${escapeHtml(t('stopped_pill'))}</span></div>`;
      } else {
        logConsole(`Backend communication error: ${err.message}`, 'error');
        bodyEl.innerHTML += `<div class="error-badge"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg> <span>Connection Error: ${escapeHtml(err.message)}</span></div>`;
      }
    } finally {
      if (inactivityTimerId) {
        clearTimeout(inactivityTimerId);
        inactivityTimerId = null;
      }
      if (hardLimitTimerId) {
        clearTimeout(hardLimitTimerId);
        hardLimitTimerId = null;
      }
      if (reader) {
        try {
          await reader.cancel();
        } catch (e) {}
        try {
          reader.releaseLock();
        } catch (e) {}
      }
      if (assistantCard && fullText) {
        updateMessageActions(assistantCard, fullText, isProofread);
      }
      state.isStreaming = false;
      state.abortController = null;
      updateStreamingUi(false);
      // Extra pojistka: odstranění visícího textu načítání
      const titleEl = document.getElementById('active-session-title');
      if (titleEl && (titleEl.textContent === 'Načítám...' || titleEl.textContent === 'Loading...')) {
        const curr = state.sessions.find(s => (s.session_id === state.sessionId || s.id === state.sessionId));
        if (curr && curr.title) {
          titleEl.textContent = curr.title;
        }
      }
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
    } finally {
      state.isStreaming = false;
      state.abortController = null;
      updateStreamingUi(false);
    }
  }

  function updateStreamingUi(isStreaming) {
    if (el.btnSend) {
      el.btnSend.style.display = isStreaming ? 'none' : 'flex';
      el.btnSend.disabled = isStreaming;
    }
    if (el.btnStop) {
      el.btnStop.style.display = isStreaming ? 'flex' : 'none';
      el.btnStop.disabled = !isStreaming;
    }
    if (el.liveStatusBadge) {
      el.liveStatusBadge.style.display = isStreaming ? 'inline-flex' : 'none';
      if (isStreaming && el.liveStatusText) {
        el.liveStatusText.textContent = t('thinking_status');
      }
    }
    if (el.promptInput) {
      el.promptInput.disabled = isStreaming;
      if (!isStreaming) {
        setTimeout(() => el.promptInput.focus(), 50);
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
    if (el.btnProofread) {
      el.btnProofread.disabled = isStreaming;
      el.btnProofread.style.opacity = isStreaming ? '0.5' : '1';
      el.btnProofread.style.pointerEvents = isStreaming ? 'none' : 'auto';
    }
    if (el.btnMic) {
      el.btnMic.disabled = isStreaming;
      el.btnMic.style.opacity = isStreaming ? '0.5' : '1';
      el.btnMic.style.pointerEvents = isStreaming ? 'none' : 'auto';
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

      if (el.cardActions) {
        el.cardActions.classList.toggle('blender-offline', !data.connected);
      }
      if (el.qaOfflineBanner) {
        el.qaOfflineBanner.style.display = data.connected ? 'none' : 'flex';
      }

      updateActiveToolsBadge();
      if (el.modalTools && el.modalTools.style.display !== 'none') {
        renderToolsInspector();
      }
    } catch (e) {
      state.blenderConnected = false;
      if (el.blenderIndicator && el.blenderStatusText) {
        el.blenderIndicator.className = 'status-indicator offline';
        el.blenderStatusText.textContent = `Blender: ${t('blender_offline')}`;
      }
      if (el.cardActions) {
        el.cardActions.classList.add('blender-offline');
      }
      if (el.qaOfflineBanner) {
        el.qaOfflineBanner.style.display = 'flex';
      }
      updateActiveToolsBadge();
      if (el.modalTools && el.modalTools.style.display !== 'none') {
        renderToolsInspector();
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
      if (!res.ok || data.status === 'error') {
        const errMsg = data.detail || data.message || data.error || `HTTP ${res.status}`;
        logConsole(`Error [${actionName}]: ${errMsg}`, 'error');
        return data;
      }
      logConsole(`Result [${actionName}]: ${JSON.stringify(data)}`, 'info');

      // Refresh snapshot and telemetry
      setTimeout(takeBlenderInspection, 500);
      return data;
    } catch (err) {
      logConsole(`Error during operation ${actionName}: ${err.message}`, 'error');
    }
  }

  const DIRECT_3D_ACTIONS = {
    'btn-qa-inspect-scene': () => takeBlenderInspection(),
    'btn-qa-mesh-audit': () => executeQuick3DAction('/api/blender/mesh-doctor?action=audit', 'Mesh Doctor Audit'),
    'btn-qa-texel-audit': () => executeQuick3DAction('/api/blender/uv-audit', 'Texel Density Audit')
  };

  function openBlenderCodeModal() {
    if (!el.modalBlenderCode) return;
    el.modalBlenderCode.style.display = 'flex';
    if (el.blenderCodeInput && !el.blenderCodeInput.value.trim()) {
      el.blenderCodeInput.value = `# Python / bpy script for Blender
import bpy

# Inspect active object
act = bpy.context.active_object
print(f"Active object: {act.name if act else 'None'}")
`;
    }
    if (el.blenderCodeInput) {
      el.blenderCodeInput.focus();
    }
  }

  function closeBlenderCodeModal() {
    if (!el.modalBlenderCode) return;
    el.modalBlenderCode.style.display = 'none';
  }

  async function executeBlenderCode() {
    if (!el.blenderCodeInput) return;
    const code = el.blenderCodeInput.value.trim();
    if (!code) {
      if (el.blenderCodeOutput && el.blenderCodeOutputText) {
        el.blenderCodeOutput.style.display = 'block';
        el.blenderCodeOutput.className = 'blender-code-output error';
        el.blenderCodeOutputText.textContent = t('blender_code_empty');
      }
      logConsole(t('blender_code_empty'), 'warn');
      return;
    }

    if (el.blenderCodeOutput && el.blenderCodeOutputText) {
      el.blenderCodeOutput.style.display = 'block';
      el.blenderCodeOutput.className = 'blender-code-output';
      el.blenderCodeOutputText.textContent = t('blender_code_running');
    }
    logConsole('Executing Python script in Blender...', 'info');

    try {
      const res = await fetch('/api/blender/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        const errorText = data.detail || data.error || data.message || `HTTP ${res.status}`;
        if (el.blenderCodeOutput && el.blenderCodeOutputText) {
          el.blenderCodeOutput.className = 'blender-code-output error';
          el.blenderCodeOutputText.textContent = `${t('blender_code_error')}${errorText}`;
        }
        logConsole(`Blender execution error: ${errorText}`, 'error');
        return;
      }

      const outputResult = data.result || data.output || JSON.stringify(data, null, 2);
      if (el.blenderCodeOutput && el.blenderCodeOutputText) {
        el.blenderCodeOutput.className = 'blender-code-output success';
        el.blenderCodeOutputText.textContent = outputResult || t('blender_code_success');
      }
      logConsole(`Blender execution success: ${typeof outputResult === 'string' ? outputResult.slice(0, 120) : 'Done'}`, 'info');
      setTimeout(takeBlenderInspection, 600);
    } catch (err) {
      if (el.blenderCodeOutput && el.blenderCodeOutputText) {
        el.blenderCodeOutput.className = 'blender-code-output error';
        el.blenderCodeOutputText.textContent = `${t('blender_code_error')}${err.message}`;
      }
      logConsole(`Blender execution network error: ${err.message}`, 'error');
    }
  }

  function sendBlenderCodeToChat() {
    if (!el.blenderCodeInput) return;
    const code = el.blenderCodeInput.value.trim();
    if (!code) {
      closeBlenderCodeModal();
      return;
    }
    closeBlenderCodeModal();
    const lang = state.language || 'en';
    const prompt = lang === 'cs'
      ? `Zkontroluj a vysvětli následující Python bpy skript pro Blender:\n\`\`\`python\n${code}\n\`\`\``
      : `Review and explain the following Python bpy script for Blender:\n\`\`\`python\n${code}\n\`\`\``;
    setPromptInputAndFocus(prompt);
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
        updateActiveToolsBadge();
        if (el.modalTools && el.modalTools.style.display !== 'none') {
          renderToolsInspector();
        }
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
        updateActiveToolsBadge();
        if (el.modalTools && el.modalTools.style.display !== 'none') {
          renderToolsInspector();
        }
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
        updateActiveToolsBadge();
        if (el.modalTools && el.modalTools.style.display !== 'none') {
          renderToolsInspector();
        }
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

    // AI Proofreading action
    if (el.btnProofread) el.btnProofread.addEventListener('click', triggerAiProofreading);

    // Context Workspace tabs
    if (el.tabBtn3d) el.tabBtn3d.addEventListener('click', () => switchInspectorTab('3d'));
    if (el.tabBtnResearch) el.tabBtnResearch.addEventListener('click', () => switchInspectorTab('research'));
    if (el.tabBtnAgent) el.tabBtnAgent.addEventListener('click', () => switchInspectorTab('agent'));

    if (el.btnOpenKnowledgeFromTab) {
      el.btnOpenKnowledgeFromTab.addEventListener('click', openRagModal);
    }

    if (el.btnClearAgentSteps) {
      el.btnClearAgentSteps.addEventListener('click', clearAgentSteps);
    }

    // 3D Blender actions
    if (el.btnTakeSnapshot) el.btnTakeSnapshot.addEventListener('click', takeBlenderInspection);
    if (el.btnRefreshTelemetry) el.btnRefreshTelemetry.addEventListener('click', () => {
      refreshBlenderStatus();
      takeBlenderInspection();
    });

    // 18-Tool Quick Command Matrix & Prefill Logic
    document.querySelectorAll('.qa-tool-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.id;

        // Visual toast warning in offline mode
        if (!state.blenderConnected) {
          showToast(t('qa_offline_toast'), 'warn');
          if (id === 'btn-qa-blender-code') {
            openBlenderCodeModal();
            return;
          }
          const lang = state.language || 'en';
          const prefill = (QA_PREFILL_PROMPTS[lang] && QA_PREFILL_PROMPTS[lang][id])
            || (QA_PREFILL_PROMPTS['en'] && QA_PREFILL_PROMPTS['en'][id])
            || btn.dataset.prompt;

          if (prefill) {
            setPromptInputAndFocus(prefill);
            logConsole(lang === 'cs'
              ? 'Blender je offline. Příkaz byl předvyplněn do chatu pro asistenta.'
              : 'Blender is offline. Command was pre-filled into chat for assistant.', 'info');
          }
          return;
        }

        // Online mode execution
        if (id === 'btn-qa-blender-code') {
          openBlenderCodeModal();
          return;
        }

        const isDirect = Boolean(DIRECT_3D_ACTIONS[id]);
        if (isDirect) {
          DIRECT_3D_ACTIONS[id]();
          return;
        }

        // Prefill into chat prompt
        const lang = state.language || 'en';
        const prefill = (QA_PREFILL_PROMPTS[lang] && QA_PREFILL_PROMPTS[lang][id])
          || (QA_PREFILL_PROMPTS['en'] && QA_PREFILL_PROMPTS['en'][id])
          || btn.dataset.prompt;

        if (prefill) {
          setPromptInputAndFocus(prefill);
        }
      });
    });

    // Blender Code Executor Modal Controls
    if (el.btnCloseBlenderCodeModal) el.btnCloseBlenderCodeModal.addEventListener('click', closeBlenderCodeModal);
    if (el.btnExecuteBlenderScript) el.btnExecuteBlenderScript.addEventListener('click', executeBlenderCode);
    if (el.btnSendCodeChat) el.btnSendCodeChat.addEventListener('click', sendBlenderCodeToChat);

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
    if (el.btnTools) el.btnTools.addEventListener('click', openToolsModal);
    if (el.btnCloseToolsModal) el.btnCloseToolsModal.addEventListener('click', closeToolsModal);
    if (el.btnEnableAllTools) el.btnEnableAllTools.addEventListener('click', () => setAllToolsEnabled(true));
    if (el.btnDisableAllTools) el.btnDisableAllTools.addEventListener('click', () => setAllToolsEnabled(false));
    if (el.btnResetToolsDefaults) el.btnResetToolsDefaults.addEventListener('click', resetToolsToDefaults);

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
      if (e.target === el.modalTools) closeToolsModal();
      if (e.target === el.modalRag) closeRagModal();
      if (e.target === el.modalSettings) closeSettingsModal();
      if (e.target === el.modalBlenderCode) closeBlenderCodeModal();
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
        closeToolsModal();
        closeBlenderCodeModal();
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
    updateActiveToolsBadge();
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
