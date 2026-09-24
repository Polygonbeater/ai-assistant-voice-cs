from search_module import vyhledej_na_internetu

# Simulace rozpoznaného textu z mikrofonu
text_od_uzivatele = "Jaké je dnes počasí v Orlové?"
print(f"🗣️ Uživatel řekl: '{text_od_uzivatele}'")

# Jednoduchá detekce, zda dotaz vyžaduje internet
klicova_slova = ["vyhledej", "najdi", "počasí", "kdo", "jaké", "co je", "internet"]
potrebuje_internet = any(slovo in text_od_uzivatele.lower() for slovo in klicova_slova)

if potrebuje_internet:
    kontext = vyhledej_na_internetu(text_od_uzivatele)
    
    # Složení finálního promptu pro LLM
    finalni_prompt = f"Uživatel se ptá: '{text_od_uzivatele}'\n\nAktuální informace z internetu:\n{kontext}\nOdpověz uživateli přirozeně a stručně na základě těchto informací."
    
    print("\n🤖 --- CO SE POŠLE LLAMA MODELU KE ZPRACOVÁNÍ ---")
    print(finalni_prompt)
    print("--------------------------------------------------")
else:
    print("Internet není potřeba, posílám dotaz rovnou do modelu.")
