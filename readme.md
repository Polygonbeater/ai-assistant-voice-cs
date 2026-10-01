# 🤖 Polygon Beater AI Assistant

Moderní, vysoce výkonný a **100% lokální hlasový AI asistent** optimalizovaný pro **český jazyk**, soukromí, nízkou latenci na vícejádrových procesorech (CPU) a přímou **automatizaci 3D modelování v aplikaci Blender**.

Projekt integruje offline inferenci velkých jazykových modelů (GGUF), špičkový modul pro přepis řeči (**Faster-Whisper** s int8 kvantizací), plynulou syntézu hlasu v reálném čase (**Pipelined Streaming TTS**), neblokující **Hands-free detekci klíčového slova** (openWakeWord) a obousměrný TCP můstek do Blender API (`bpy`).

---

## 🌟 Klíčové vlastnosti (Features)

### ⚡ 1. Maximální výkon na CPU a plné soukromí
* **Žádný cloud, žádné API klíče:** Všechna data, audio nahrávky i textové konverzace zůstávají výhradně ve vašem počítači.
* **Dynamická detekce CPU jader:** Asistent pomocí knihovny `psutil` automaticky zjišťuje přesný počet **fyzických CPU jader** (bez hyperthreadingu/SMT) a přiřazuje optimální počet vláken (`n_threads`), čímž předchází degradaci výkonu a zbytečnému kontextovému přepínání.
* **Optimalizovaný llama.cpp engine:** Rychlý běh na CPU s `use_mmap=True`, bezpečně zakázaným `mlock`, `n_batch=512` a dynamickou kalkulací kontextu (`n_ctx`) optimalizovanou pro modely řady **Qwen 2.5** i **GLM-4** tak, aby neplýtvaly operační pamětí RAM.

### 🎙️ 2. Moderní hlasový ekosystém nové generace
* **Faster-Whisper (int8 CTranslate2):** Migrace z původního Whisperu na engine CTranslate2. S 8-bitovou kvantizací běží přepis češtiny na CPU až 4× rychleji při zachování vysoké přesnosti, s deterministickým vzorkováním (`beam_size=1`, `temperature=0.0`) a robustní filtrací ticha/halucinací.
* **Plynulé streamované TTS (Pipelined Streaming):** Inferenční smyčka LLM vrací vygenerovaný text po ucelených větách a logických blocích (podle interpunkce). Asynchronní syntetizér (**Coqui TTS**) a přehrávač (**PyAudio**) začínají mluvit okamžitě po dokončení první věty, zatímco LLM na pozadí stále počítá zbytek odpovědi.
* **Okamžité přerušení (Barge-in):** Pokud uživatel začne mluvit nebo klikne na zastavení, zvuková fronta se okamžitě vyprázdní a syntéza se bez prodlevy ukončí.
* **Hands-free režim (openWakeWord):** Asistent neustále naslouchá na pozadí v odděleném daemon vlákně. Po zachycení fráze (např. *"Hey Jarvis"*) zazní potvrzovací tón (**chime**) a automaticky se aktivuje nahrávání s VAD.
* **Silero VAD:** Pokročilá detekce řečové aktivity zajišťuje přesné oříznutí ticha a automatické ukončení záznamu ihned po domluvení.

### 🎨 3. Hlasová automatizace pro Blender 3D (TCP Bridge)
* **Generování Python kódu (bpy):** Pomocí specializovaného systémového promptu asistent rozpozná 3D modelovací či editační požadavek (např. *"vycentruj pivoty a aplikuj scale všem vybraným meshům"*) a vygeneruje čistý Python kód bez zbytečné omáčky.
* **Stabilní TCP Socket spojení:** Asistent komunikuje s Blenderem přes lokální TCP spojení (`127.0.0.1:9876`).
* **Zaručený běh v hlavním vlákně:** Přijímací skript v Blenderu (`blender_receiver.py`) využívá oficiální `bpy.app.timers`. Kód z LLM se provede bezpečně v hlavním vlákně Blenderu, což eliminuje pády aplikace, nechtěná zamrznutí i kolize s OpenGL/Vulkan vlákny.
* **Okamžitý 3D redraw:** Po vykonání příkazu se automaticky překreslí 3D viewport a asistent hlasem i v chatu oznámí výsledek operace.

### 🖥️ 4. Moderní GUI a doplňkové nástroje
* **Tmavý motiv (CustomTkinter / Tkinter):** Přehledné rozhraní s bočním panelem pro správu historie konverzací (`sessions/`), rychlým vyhledáváním a možností exportu.
* **Markdown & živé odkazy:** Plné zobrazení formátovaného textu včetně klikatelných internetových odkazů.
* **Online režim (Web Search & RSS):** Možnost zapnutí živého ověřování aktuálních událostí (ČT24, Google News RSS) s extrakcí článků přes `trafilatura`.
* **Analýza dokumentů (RAG):** Okamžité nahrávání a sumarizace vlastních textových i PDF souborů (`document_service.py`).
* **Metodické prompty:** Přednastavené expertní rámce (např. *Assumption Audit* pro kritickou oponenturu myšlenek).

---

## 📋 Systémové požadavky

* **Operační systém:** Linux (testováno na Ubuntu / Debian / Manjaro) nebo macOS / Windows (WSL2).
* **Python:** 3.10, 3.11 nebo 3.12.
* **Procesor:** Moderní vícejádrový procesor (doporučeno min. 4 fyzická jádra, např. AMD Ryzen nebo Intel Core i5/i7/i9).
* **RAM:** Minimálně 16 GB RAM (pro plynulý běh 7B/9B GGUF modelů).
* **Software pro 3D automatizaci:** Blender 3.0+ (volitelné).

---

## ⚙️ Instalace krok za krokem

### 1. Klonování repozitáře a virtuální prostředí
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

python3 -m venv venv
source venv/bin/activate
```

### 2. Instalace systémových knihoven (Linux)
Pro správné fungování zvukového vstupu/výstupu a práce se soubory je zapotřebí nainstalovat systémový balíček PortAudio a FFmpeg:
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev ffmpeg
```

### 3. Instalace Python závislostí
Nainstalujte všechny potřebné knihovny:
```bash
pip install -r requirements.txt
```

> **Důležité klíčové balíčky obsažené v requirements:**
> * `faster-whisper` – Akcelerovaný přepis řeči s CTranslate2 (int8 podpora).
> * `openwakeword` & `onnxruntime` – Lehká offline detekce aktivačního slova.
> * `psutil` – Dynamická inspekce fyzické topologie CPU jader.
> * `llama-cpp-python` – Vysoce optimalizovaný runtime pro GGUF modely.
> * `TTS` (Coqui TTS) & `PyAudio` – Lokální syntéza řeči s českým modelem.

### 4. Stažení LLM modelu a konfigurace
Stáhněte si libovolný GGUF model podporující instrukce v češtině (např. *Qwen 2.5 7B Instruct* nebo *GLM-4 9B Chat*) a vložte jej do složky `models/`:
```bash
mkdir -p models
# Příklad: zkopírujte stažený model do models/glm-4-9b-chat.Q4_K_M.gguf
```

Zkopírujte vzorový konfigurační soubor:
```bash
cp config.example.json config.json
```

V souboru `config.json` můžete zkontrolovat cesty a nastavení:
```json
{
  "whisper": {
    "model": "medium",
    "language": "cs"
  },
  "llama": {
    "model": "models/glm-4-9b-chat.Q4_K_M.gguf",
    "max_tokens": 150
  },
  "tts": {
    "model_name": "tts_models/cs/cv/vits",
    "gpu": false
  },
  "audio": {
    "device_index": -1,
    "max_recording_time": 15
  },
  "silero_vad": {
    "sample_rate": 16000,
    "threshold": 0.3,
    "silence_duration_ms": 2000
  },
  "wakeword": {
    "enabled": false,
    "model": "hey_jarvis",
    "threshold": 0.5
  },
  "blender": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 9876
  }
}
```

---

## 🚀 Návod k použití

### 1. Spuštění asistenta
Aktivujte virtuální prostředí a spusťte grafické rozhraní:
```bash
source venv/bin/activate
python gui.py
```

---

### 2. Aktivace a práce v režimu Hands-Free
Hands-free režim umožňuje ovládat asistenta čistě hlasem bez nutnosti klikat na tlačítko "Naslouchat".

1. **Aktivace v rozhraní:** V dolním panelu aplikace zaškrtněte políčko **`🎙️ Hands-free (Hey Jarvis)`**.
2. **Naslouchání na pozadí:** V odděleném vlákně se spustí úsporný engine `openWakeWord`. V hlavním status baru se zobrazí hlášení, že asistent očekává klíčové slovo.
3. **Probuzení:** Vyslovte zřetelně aktivační frázi:
   > *"Hey Jarvis"*
4. **Potvrzovací signál:** Aplikace okamžitě přehraje krátký melodický tón (**chime**) potvrzující, že asistent zachytil oslovení a začíná poslouchat.
5. **Vyslovení dotazu:** Řekněte svůj dotaz v češtině (např. *"Jaký je rozdíl mezi procedurálním a parametrickým modelováním?"*).
6. **Automatické zpracování:** Jakmile domluvíte, Silero VAD detekuje konec promluvy, mikrofon se uzavře a asistent ihned spustí přepis řeči a začne streamovat mluvenou odpověď.
7. **Deaktivace:** Kdykoliv můžete odškrtnout volbu Hands-free a vrátit se k manuálnímu spouštění tlačítkem.

---

### 3. Automatizace v Blenderu 3D (Krok za krokem)
Asistent dokáže přijímat přirozené příkazy v češtině, převádět je na bezpečný Python kód pro Blender API (`bpy`) a vzdáleně je v Blenderu vykonávat.

#### Krok A: Spuštění přijímacího skriptu v Blenderu
1. Spusťte **Blender** (libovolnou verzi 3.x nebo 4.x) a otevřete existující scénu nebo nový soubor.
2. V horní liště přepněte na layout **Scripting** (nebo v libovolném okně otevřete **Text Editor**).
3. Klikněte na tlačítko **Open** (Otevřít) a vyberte soubor `blender_receiver.py` z kořenového adresáře tohoto projektu.
4. Klikněte na tlačítko ▶ **Run Script** (nebo stiskněte klávesovou zkratku `Alt + P`).
5. V systémové konzoli Blenderu (*Window -> Toggle System Console*) se zobrazí potvrzení:
   ```text
   ✅ [AI-Blender] TCP Server naslouchá na 127.0.0.1:9876...
   ```
   > 💡 *Server běží neblokujícím způsobem na pozadí a úlohy spouští přes `bpy.app.timers` v hlavním vlákně Blenderu. Rozhraní Blenderu zůstává 100% plynulé a ovladatelné.*

#### Krok B: Zadání příkazu asistentovi
V asistentovi (hlasem přes Hands-free / tlačítko, nebo napsáním do textového pole) vyslovte či napište svůj záměr:
* *"Vytvoř kruh z osmi kostek a dej každé náhodnou výšku."*
* *"Vycentruj pivoty všem vybraným objektům a nastav jim jednotný scale."*
* *"Přidej do scény bodové světlo nad vybraný objekt a zbarvi ho do tepla."*
* *"Nastav všem označeným meshům hladké stínování (shade smooth)."*

#### Krok C: Vykonání a okamžitá vizualizace
1. Asistent automaticky detekuje, že se jedná o manipulaci v Blenderu.
2. LLM vygeneruje přesný kód pro `bpy`.
3. Kód je odeslán na port `9876`.
4. Blender kód bezpečně provede, automaticky označí **3D Viewport k překreslení (tag_redraw)** a asistent potvrdí úspěšné dokončení akce.

#### Krok D: Ukončení serveru v Blenderu
Pokud chcete server v Blenderu zastavit, spusťte v Text Editoru Blenderu:
```python
import blender_receiver
blender_receiver.stop_server()
```
Server se také automaticky ukončí při zavření Blenderu.

---

## 📁 Struktura projektu

| Soubor / Adresář | Význam a funkce |
| :--- | :--- |
| `gui.py` | Hlavní desktopové grafické rozhraní (Tkinter) se streamováním odpovědí, správou sezení a přepínačem Hands-free. |
| `llama_module.py` | Správa LLM inference přes `llama.cpp`, dynamická detekce jader procesoru, chunkování vět a detekce Blender povelů. |
| `stt_module.py` | Rychlý přepis řeči přes **Faster-Whisper** s `int8` kvantizací a ošetřením ticha. |
| `tts_module.py` | Asynchronní syntéza řeči s **Coqui TTS**, pipelined přehrávač (`TTSStreamPlayer`) s okamžitým přerušením. |
| `audio.py` | Záznam zvuku z mikrofonu, filtrace přes Silero VAD, potvrzovací znělka (**chime**) a listener pro `openWakeWord`. |
| `blender_connector.py` | Klientský TCP konektor odesílající vygenerovaný Python kód do Blenderu. |
| `blender_receiver.py` | Bezpečný TCP server spouštěný přímo v Blenderu (`bpy.app.timers`). |
| `web_search.py` | Online rešerše, parsování RSS (ČT24, Google News) a čištění HTML článků přes `trafilatura`. |
| `document_service.py` | Extrakce textu a RAG operace nad nahranými PDF a textovými soubory. |
| `history_repository.py` | Ukládání a načítání historie konverzací ve formátu JSON v adresáři `sessions/`. |
| `prompts/` | Systémové prompty pro analytické úlohy a specializované metodiky. |

---

## 🛠️ Řešení potíží (Troubleshooting)

* **Mikrofon nezaznamenává zvuk nebo hlásí chybu:**
  * Ověřte index vašeho vstupního zařízení. V rozhraní můžete v poli `Vstup:` zadat konkrétní ID zvukové karty (nebo ponechat `-1` pro výchozí systémové zařízení).
* **Hands-free nereaguje na aktivační frázi:**
  * Ujistěte se, že je fráze vyslovena srozumitelně (*"Hey Jarvis"*). Práh citlivosti (`threshold`) můžete upravit v `config.json` v sekci `"wakeword": { "threshold": 0.45 }`.
* **Chyba spojení s Blenderem (`Blender TCP spojení selhalo`):**
  * Zkontrolujte, zda jste v Blenderu nezapomněli spustit skript `blender_receiver.py` přes `Run Script` (`Alt + P`).
  * Ověřte, že v `config.json` i v `blender_receiver.py` souhlasí port (výchozí `9876`).
* **Vysoké vytížení RAM při načítání modelu:**
  * Moduly automaticky počítají optimální `n_ctx` na základě modelu. Pro 8 GB/16 GB systémy doporučujeme používat modely o velikosti 7B s kvantizací `Q4_K_M`.

---

## 💖 Autor a licence

* **Autor:** Vítězslav Koneval ([Polygon Beater](https://github.com/Polygonbeater))
* **Licence:** Vydáno pod otevřenou licencí [MIT License](LICENSE).
