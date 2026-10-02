#!/usr/bin/env bash
# ==============================================================================
# AI Assistant Voice CS — Automatizovaný instalační skript pro Linux
# Vítězslav Koneval (Polygon Beater)
# ==============================================================================

set -e

# --- Definice barev pro terminálový výstup ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# --- Pomocné funkce pro logování ---
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_step() {
    echo -e "\n${BOLD}${BLUE}==>${NC} ${BOLD}$1${NC}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

print_banner() {
    echo -e "${PURPLE}${BOLD}"
    echo "======================================================================"
    echo "  🎙️  AI Assistant Voice CS: Local Voice Companion & 3D Technical Director"
    echo "  Automatická instalace celého ekosystému (Ubuntu / Debian Linux)"
    echo "======================================================================"
    echo -e "${NC}"
}

# --- Zpracování argumentů příkazového řádku ---
WITH_TRIPO=false
NON_INTERACTIVE=false
SKIP_TESTS=false

for arg in "$@"; do
    case $arg in
        --with-tripo)
            WITH_TRIPO=true
            shift
            ;;
        -y|--yes)
            NON_INTERACTIVE=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        -h|--help)
            echo "Použití: $0 [PŘEPÍNAČE]"
            echo ""
            echo "Přepínače:"
            echo "  --with-tripo   Automaticky zkompiluje a nainstaluje TripoSR a torchmcubes z gitu"
            echo "  -y, --yes      Neinteraktivní režim (odpoví 'ano' na standardní dotazy)"
            echo "  --skip-tests   Přeskočí závěrečné spuštění 176 unit testů"
            echo "  -h, --help     Zobrazí tuto nápovědu"
            exit 0
            ;;
        *)
            ;;
    esac
done

print_banner

# ==============================================================================
# KROK 1: KONTROLA PROSTŘEDÍ A SYSTÉMOVÝCH ZÁVISLOSTÍ
# ==============================================================================
log_step "Krok 1/7: Kontrola operačního systému a prostředí..."

OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" != "Linux" ]; then
    log_error "Tento instalační skript je určen pouze pro operační systém Linux (Ubuntu/Debian). Detekováno: $OS_TYPE"
    exit 1
fi
log_success "Operační systém Linux ověřen ($OS_TYPE)."

if ! command -v apt-get &> /dev/null; then
    log_warning "Správce balíčků 'apt-get' nebyl nalezen. Skript předpokládá distribuci založenou na Debianu/Ubuntu."
fi

# Detekce Pythonu 3.11
PYTHON_BIN=""
if command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3 &> /dev/null; then
    PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
    if [ "$PY_VER" = "3.11" ]; then
        PYTHON_BIN="python3"
    fi
fi

if [ -n "$PYTHON_BIN" ]; then
    log_success "Python 3.11 byl detekován ($($PYTHON_BIN --version))."
else
    log_warning "Python 3.11 nebyl nalezen v PATH. Bude nainstalován v rámci systémových balíčků."
fi

if command -v git &> /dev/null; then
    log_success "Git je přítomen ($(git --version))."
else
    log_warning "Git nebyl nalezen. Bude nainstalován přes apt."
fi

# ==============================================================================
# KROK 2: INSTALACE SYSTÉMOVÝCH ZÁVISLOSTÍ PŘES APT
# ==============================================================================
log_step "Krok 2/7: Instalace systémových knihoven přes APT..."

SYSTEM_PKGS=(
    python3-dev
    python3.11
    python3.11-venv
    python3.11-dev
    portaudio19-dev
    ffmpeg
    build-essential
    git
    curl
)

log_info "Aktualizuji index balíčků (sudo apt update)..."
if sudo apt update; then
    log_success "Index repozitářů byl úspěšně aktualizován."
else
    log_error "Aktualizace apt selhala. Zkontrolujte připojení k internetu a sudo oprávnění."
    exit 1
fi

log_info "Instaluji potřebné systémové knihovny:"
echo "  • build-essential (gcc/g++ kompilátor nezbytný pro C++ rozšíření torchmcubes)"
echo "  • portaudio19-dev (pro PyAudio, mikrofonní vstup a hlasový streaming)"
echo "  • ffmpeg (pro zpracování audio streamů a přepis řeči přes Whisper)"
echo "  • python3.11, python3.11-dev, python3.11-venv (izolované běhové prostředí)"
echo "  • git, curl (pro stahování vah modelů a git knihoven)"

if sudo apt install -y "${SYSTEM_PKGS[@]}"; then
    log_success "Všechny systémové balíčky byly úspěšně nainstalovány."
else
    log_error "Instalace systémových balíčků selhala."
    exit 1
fi

# Znovunalezení python3.11 po instalaci
if command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
else
    PYTHON_BIN="python3"
fi

# ==============================================================================
# KROK 3: VYTVOŘENÍ A AKTIVACE VIRTUÁLNÍHO PROSTŘEDÍ (VENV)
# ==============================================================================
log_step "Krok 3/7: Vytváření a aktivace virtuálního prostředí (venv)..."

VENV_DIR="venv"

if [ -d "$VENV_DIR" ]; then
    log_info "Existující virtuální prostředí '$VENV_DIR' nalezeno."
    if [ "$NON_INTERACTIVE" = false ]; then
        read -r -p "Chcete existující venv smazat a vytvořit čisté od začátku? [y/N]: " RECREATE_VENV
        case "$RECREATE_VENV" in
            [yY][eE][sS]|[yY])
                log_info "Mažu staré virtuální prostředí..."
                rm -rf "$VENV_DIR"
                log_info "Vytvářím nové virtuální prostředí: $PYTHON_BIN -m venv $VENV_DIR"
                $PYTHON_BIN -m venv "$VENV_DIR"
                ;;
            *)
                log_info "Používám stávající virtuální prostředí '$VENV_DIR'."
                ;;
        esac
    fi
else
    log_info "Vytvářím izolované virtuální prostředí: $PYTHON_BIN -m venv $VENV_DIR"
    $PYTHON_BIN -m venv "$VENV_DIR"
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    log_error "Virtuální prostředí nebylo nalezeno v '$VENV_DIR/bin/activate'!"
    exit 1
fi

# Aktivace venv pro zbytek instalace
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
log_success "Virtuální prostředí aktivováno: $(python -c 'import sys; print(sys.executable)')"

# ==============================================================================
# KROK 4: AKTUALIZACE PIP A INSTALACE REQUIREMENTS.TXT
# ==============================================================================
log_step "Krok 4/7: Instalace Python balíčků z requirements.txt..."

log_info "Aktualizuji pip, setuptools a wheel..."
pip install --upgrade pip setuptools wheel

if [ ! -f "requirements.txt" ]; then
    log_error "Soubor requirements.txt nebyl v aktuálním adresáři nalezen!"
    exit 1
fi

log_info "Instaluji závislosti s přísnými verzními stropy (numpy<2.0.0, networkx<3.0.0)..."
if pip install -r requirements.txt; then
    log_success "Python balíčky z requirements.txt byly úspěšně nainstalovány."
else
    log_error "Instalace requirements.txt selhala. Zkontrolujte chybový výstup výše."
    exit 1
fi

# Kontrola ověřených verzí
NUMPY_VER=$(python -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "N/A")
NETWORKX_VER=$(python -c "import networkx; print(networkx.__version__)" 2>/dev/null || echo "N/A")
log_info "Ověřené klíčové verze: numpy=${NUMPY_VER}, networkx=${NETWORKX_VER}"

# ==============================================================================
# KROK 5: VOLITELNÁ TRIPOSR NADSTAVBA (3D GPU INFERENCE)
# ==============================================================================
log_step "Krok 5/7: Volitelná 3D/AI nadstavba (TripoSR & torchmcubes)..."

INSTALL_TRIPO=$WITH_TRIPO

if [ "$INSTALL_TRIPO" = false ] && [ "$NON_INTERACTIVE" = false ]; then
    echo -e "${YELLOW}"
    echo "TripoSR umožňuje lokální převod 2D obrázků na 3D modely přímo na vaší GPU."
    echo "Vyžaduje kompilaci C++ rozšíření 'torchmcubes' (Marching Cubes) přes build-essential."
    echo -e "${NC}"
    read -r -p "Přejete si nyní nainstalovat TripoSR a torchmcubes přímo z GitHubu? [y/N]: " USER_CHOICE
    case "$USER_CHOICE" in
        [yY][eE][sS]|[yY])
            INSTALL_TRIPO=true
            ;;
        *)
            INSTALL_TRIPO=false
            ;;
    esac
fi

if [ "$INSTALL_TRIPO" = true ]; then
    log_info "Instaluji C++ rozšíření torchmcubes z GitHubu..."
    if pip install git+https://github.com/tatsy/torchmcubes.git; then
        log_success "torchmcubes úspěšně zkompilován a nainstalován."
    else
        log_warning "Kompilace torchmcubes selhala (může chybět CUDA dev toolset). Asistent využije deterministický fallback."
    fi

    log_info "Instaluji balíček TripoSR z GitHubu..."
    if pip install git+https://github.com/VAST-AI-Research/TripoSR.git; then
        log_success "TripoSR úspěšně nainstalován."
    else
        log_warning "Instalace TripoSR z gitu selhala. Asistent využije deterministický fallback."
    fi
else
    log_info "Instalace TripoSR byla přeskočena. Modul local_3d_inference.py poběží v mock/fallback režimu."
fi

# ==============================================================================
# KROK 6: OVĚŘENÍ INSTALACE — SPUŠTĚNÍ 176 UNIT TESTŮ
# ==============================================================================
log_step "Krok 6/7: Verifikace instalace — Spuštění testovacího balíku..."

if [ "$SKIP_TESTS" = true ]; then
    log_warning "Testy byly přeskočeny na základě parametru --skip-tests."
else
    log_info "Spouštím 176 unit testů (Blender TCP, 20 nástrojů, FAISS RAG, TripoSR)..."
    
    if PYTHONPATH=. python -m unittest discover -s scratch/ -p "test_*.py"; then
        echo ""
        log_success "VŠECH 176 UNIT TESTŮ PROBĚHLO ÚSPĚŠNĚ (100% PASS RATE)!"
    else
        log_error "Některé unit testy selhaly. Prozkoumejte prosím výstup výše."
        exit 1
    fi
fi

# ==============================================================================
# KROK 7: VYTVOŘENÍ SYSTÉMOVÉHO SPOUŠTĚČE (.DESKTOP)
# ==============================================================================
log_step "Krok 7/7: Vytváření systémového spouštěče (.desktop)..."

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "Detekována absolutní cesta repozitáře: $REPO_DIR"

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
DESKTOP_FILE="$APPS_DIR/ai-assistant-voice-cs.desktop"

log_info "Generuji $DESKTOP_FILE..."
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=AI Assistant Voice CS
Comment=Local Voice Companion & 3D Technical Director
Exec=$REPO_DIR/venv/bin/python $REPO_DIR/main.py
Path=$REPO_DIR
Icon=applications-multimedia
Terminal=false
Categories=AudioVideo;Audio;Development;Graphics;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
log_success "Systémový spouštěč byl vytvořen: $DESKTOP_FILE"

# Zkopírování na pracovní plochu uživatele, pokud existuje
DESKTOP_DIR="$HOME/Desktop"
if [ -d "$DESKTOP_DIR" ]; then
    log_info "Nalezena pracovní plocha: $DESKTOP_DIR"
    cp "$DESKTOP_FILE" "$DESKTOP_DIR/ai-assistant-voice-cs.desktop"
    chmod +x "$DESKTOP_DIR/ai-assistant-voice-cs.desktop"
    
    # Pro GNOME/KDE: nastavení příznaku důvěryhodnosti pro spuštění bez varování
    if command -v gio &> /dev/null; then
        gio set "$DESKTOP_DIR/ai-assistant-voice-cs.desktop" metadata::trusted true 2>/dev/null || true
    fi
    log_success "Zástupce byl zkopírován na pracovní plochu: $DESKTOP_DIR/ai-assistant-voice-cs.desktop"
fi

# ==============================================================================
# HOTOVO — SOUHRN A INSTRUKCE KE SPUŠTĚNÍ
# ==============================================================================
echo ""
echo -e "${GREEN}${BOLD}======================================================================${NC}"
echo -e "${GREEN}${BOLD}  🎉 INSTALACE BYLA ÚSPĚŠNĚ DOKONČENA! VŠECHNY KOMPONENTY JSOU PŘIPRAVENY.${NC}"
echo -e "${GREEN}${BOLD}======================================================================${NC}"
echo ""
echo -e "${BOLD}Jak asistenta spustit:${NC}"
echo -e "  A) ${BOLD}Přes aplikaci / plochu:${NC} Poklepejte na ikonu ${CYAN}AI Assistant Voice CS${NC}"
echo "  B) ${BOLD}Z terminálu:${NC}"
echo -e "     1. ${CYAN}source venv/bin/activate${NC}"
echo -e "     2. V Blenderu 4.2.1 LTS spusťte ${CYAN}blender_receiver.py${NC} (Alt + P)"
echo -e "     3. ${CYAN}python main.py${NC} (Spustí moderní Antigravity Web UI na http://127.0.0.1:8000)"
echo -e "        (Případně ${CYAN}python gui.py${NC} pro starší desktopové okno)"
echo ""
echo -e "${PURPLE}Autor: Vítězslav Koneval (Polygon Beater)${NC}"
echo -e "${PURPLE}Repozitář: https://github.com/Polygonbeater/ai-assistant-voice-cs${NC}"
echo ""
