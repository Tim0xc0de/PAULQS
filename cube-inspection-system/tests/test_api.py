# API tests
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def test_health_check():
    response = requests.get("http://127.0.0.1:8000/")
    print(f"Health Check: {response.status_code} - {response.json()}")

def test_create_configuration():
    """Testet das Senden einer Würfel-Soll-Konfiguration (FR1)."""
    payload = {
        "target_color_left": "rot",
        "target_color_right": "grün",
        "target_dots": 4
    }
    
    response = requests.post(f"{BASE_URL}/config", json=payload)
    
    if response.status_code == 200:
        print("✅ Erfolg: Konfiguration wurde gespeichert!")
        print(f"Antwort vom Server: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"❌ Fehler: Status {response.status_code}")
        print(response.text)

def test_get_inspections():
    """Prüft das Abrufen der Prüfergebnisse (FR8)."""
    response = requests.get(f"{BASE_URL}/inspections")
    
    if response.status_code == 200:
        results = response.json()
        print(f"✅ Erfolg: {len(results)} Prüfergebnisse geladen!")
        if results:
            print(f"Neuestes Ergebnis: {results[0]}")
    else:
        print(f"❌ Fehler beim Abrufen: {response.status_code}")

if __name__ == "__main__":
    print("Starte API-Tests...")
    test_health_check()
    print("-" * 20)
    test_create_configuration()
    print("-" * 20)
    test_get_inspections()