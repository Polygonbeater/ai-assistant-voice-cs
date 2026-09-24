import requests
import json
import time
import sys
import os
import re
from concurrent.futures import ThreadPoolExecutor
from chat import initialize_llama

FREELANCER_TOKEN = "0yFwSkJtJRc9iW6M7CVYUqXIPVIJKc"
SEARCH_QUERIES = ["3d rendering", "3d modeling", "blender", "product visualization", "3d animation"]
BANNED_COUNTRIES = ["India", "Pakistan", "Bangladesh", "Nigeria", "Kenya"]
ALLOWED_CURRENCIES = ["USD", "EUR", "AUD", "GBP", "CAD", "CZK"]
MIN_BUDGET = 80
MIN_BUDGET_CZK = 2000
HISTORY_FILE = "seen_projects.json"
LEADS_FILE = "zaznamy_leads.md"

def load_seen_projects():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_seen_projects(seen_set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f)

def append_to_leads_markdown(title, url, budget, currency, country, taktika):
    mode = "a" if os.path.exists(LEADS_FILE) else "w"
    with open(LEADS_FILE, mode, encoding="utf-8") as f:
        if mode == "w":
            f.write("# 🎯 Přehled schválených 3D zakázek (Polygon Beater)\n\n")
        f.write(f"### [{title}]({url})\n")
        f.write(f"- **Rozpočet:** {budget} {currency}\n")
        f.write(f"- **Klient:** {country}\n")
        f.write(f"- **Taktika:** {taktika}\n\n---\n")

def fetch_freelancer_projects(query):
    url = "https://www.freelancer.com/api/projects/0.1/projects/active"
    params = {
        "query": query, "compact": "false", "languages": "en", 
        "limit": 15, "job_details": "true", "location_details": "true"
    }
    headers = {"freelancer-oauth-v1": FREELANCER_TOKEN}
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 401:
            print("❌ CHYBA: Tvůj API Token vypršel.")
            sys.exit(1)
        response.raise_for_status()
        return response.json().get("result", {}).get("projects", [])
    except Exception as e:
        return []

def is_clean_blender_project(title, desc):
    text = (title + " " + desc).lower()
    banned_keywords = [
        "wordpress", "divi", "seo", "python", "fastapi", "php", "c++", "c#", 
        "java", "backend", "api", "logo", "2d", "autocad", "plugin", "hosting",
        "content writing", "translator", "database", "sql"
    ]
    for b in banned_keywords:
        if b in text:
            return False
    return True

def parse_model_output(output_text):
    zaver = "ZAMÍTNUTO"
    taktika = "-"
    
    for line in output_text.split('\n'):
        if "ZAVER:" in line or "ZÁVĚR:" in line:
            if "SCHVÁLENO" in line.upper():
                zaver = "SCHVÁLENO"
        if "TAKTIKA:" in line:
            parts = line.split("TAKTIKA:", 1)
            if len(parts) > 1 and parts[1].strip():
                taktika = parts[1].strip()
                
    return zaver, taktika

def evaluate_project(llm, project, country):
    title = project.get("title", "")
    desc = project.get("description", "")
    
    if not is_clean_blender_project(title, desc):
        return "ZAMÍTNUTO", "-"

    prompt = (
        f"KLIENT: {country}\nNÁZEV: {title}\nPOPIS: {desc}\n\n"
        f"NAPIŠ ODPOVĚĎ PŘESNĚ TAKTO:\n"
        f"ANALYZA: [Stručně česky vysvětli, zda jde o čistou 3D tvorbu v Blenderu/modelování.]\n"
        f"ZAVER: [Napiš buď 'SCHVÁLENO' nebo 'ZAMÍTNUTO']\n"
        f"TAKTIKA: [Pokud je ZAVER SCHVÁLENO, napiš 1 větu česky s taktickou výhodou pro 3D. Pokud ZAMÍTNUTO, napiš '-']"
    )
    
    system_prompt = (
        "Jsi přísný filtr pro 3D grafika. Vítězslav tvoří VÝHRADNĚ 3D grafiku (Blender, modelování, vizualizace, animace). "
        "ZAMÍTNI cokoliv spojené s webdesignem, kódováním, 2D logy nebo backendem. "
        "Odpovídej stručně ve formátu ANALYZA, ZAVER, TAKTIKA."
    )
    
    try:
        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
            temperature=0.0,
            top_p=0.7,
            repeat_penalty=1.08,
            stream=False
        )
        output_text = response["choices"][0]["message"]["content"]
        return parse_model_output(output_text)
    except Exception:
        return "ZAMÍTNUTO", "-"

if __name__ == "__main__":
    print("🚀 Spouštím Jarvis Sentinel (Trvalý 24/7 3D strážce trhu)")
    
    
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"Chyba při načítání config.json: {e}")
        sys.exit(1)
        
    print("Načítám Qwen model do paměti...")
    llm = initialize_llama(cfg)
    
    print("\n🛡️ Sentinel je aktivní. Skenuji každých 5 minut. Stiskni Ctrl+C pro ukončení.")
    
    try:
        while True:
            timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{timestamp_str}] 🔄 Skenuji 3D trh na Freelanceru...")
            
            seen_projects = load_seen_projects()
            all_projects = []
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = executor.map(fetch_freelancer_projects, SEARCH_QUERIES)
                for res in results:
                    if res:
                        all_projects.extend(res)
                        
            new_count = 0
            for p in all_projects:
                project_id = str(p.get("id"))
                if project_id in seen_projects:
                    continue
                    
                seen_projects.add(project_id)
                save_seen_projects(seen_projects)
                
                title = p.get("title", "Bez názvu")
                country = p.get("owner", {}).get("location", {}).get("country", {}).get("name", "Unknown")
                budget_min = p.get("budget", {}).get("minimum", 0)
                currency = p.get("currency", {}).get("code", "USD")
                
                if country in BANNED_COUNTRIES or currency not in ALLOWED_CURRENCIES:
                    continue
                if currency == "CZK" and budget_min < MIN_BUDGET_CZK:
                    continue
                elif currency != "CZK" and budget_min < MIN_BUDGET:
                    continue
                    
                new_count += 1
                seo_url = p.get('seo_url', '')
                url = f"https://www.freelancer.com/projects/{seo_url}"
                
                submitted_timestamp = int(p.get('time_submitted', time.time()))
                age_seconds = int(time.time()) - submitted_timestamp
                if age_seconds < 3600:
                    age_str = f"🔥 Před {int(age_seconds / 60)} minutami"
                elif age_seconds < 86400:
                    age_str = f"⏳ Před {int(age_seconds / 3600)} hodinami"
                else:
                    age_str = f"📅 Před {int(age_seconds / 86400)} dny"

                print(f"\n🎯 NALEZENO: {title} ({age_str})")
                print(f"🔗 Odkaz: {url}")
                
                zaver, taktika = evaluate_project(llm, p, country)
                
                if zaver == "SCHVÁLENO":
                    print(f"✅ SCHVÁLENO | Taktika: {taktika}")
                    append_to_leads_markdown(title, url, budget_min, currency, country, taktika)
                    os.system(f'notify-send "Polygon Beater Sentinel" "Nová 3D zakázka: {title}" 2>/dev/null')
                else:
                    print("❌ Odmítnuto (filtr/AI).")
                    
            print(f"   -> Zpracováno {new_count} nových projektů. Další sken za 45 sekund...")
            time.sleep(45)
            
    except KeyboardInterrupt:
        print("\n🛑 Sentinel byl manuálně ukončen.")
