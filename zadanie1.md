# Sprawozdanie - Część Obowiązkowa

**Laboratorium:** Programowanie Aplikacji w Chmurze Obliczeniowej

**Zadanie:** 1

**Autor:** Jan Krzemiński

---

## 1. Kod oprogramowania (Aplikacja pogodowa)
Do realizacji zadania wybrano język Python, wykorzystując wyłącznie biblioteki standardowe (brak konieczności instalacji zewnętrznych zależności przez `pip`, co minimalizuje ryzyko wystąpienia podatności CVE). Aplikacja serwuje prosty interfejs HTML, komunikuje się z publicznym API Open-Meteo i zostawia ślad w logach przy starcie.

**Plik `main.py`:**
```python
import http.server
import socketserver
import urllib.request
import json
import datetime
from urllib.parse import parse_qs

# --- KONFIGURACJA ---
PORT = 8080
AUTHOR = "Jan Krzemiński"

# Predefiniowana lista miast (wymagane współrzędne dla API Open-Meteo)
CITIES = {
    "Warszawa (Polska)": ("52.2297", "21.0122"),
    "Londyn (UK)": ("51.5085", "-0.1257"),
    "Tokio (Japonia)": ("35.6895", "139.6917"),
    "Nowy Jork (USA)": ("40.7143", "-74.0060")
}

class WeatherHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Specjalny endpoint dla mechanizmu Docker HEALTHCHECK
        if self.path == '/health':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
            
        # Zwykły GET - wyświetlenie formularza
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        
        html = """
        <html><head><title>Pogodynka Chmurowa</title><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
            <h2>Wybierz lokalizację, aby sprawdzić pogodę</h2>
            <form method="POST" action="/">
                <select name="city" style="padding: 5px; font-size: 16px;">
                    <option value="Warszawa (Polska)">Warszawa (Polska)</option>
                    <option value="Londyn (UK)">Londyn (UK)</option>
                    <option value="Tokio (Japonia)">Tokio (Japonia)</option>
                    <option value="Nowy Jork (USA)">Nowy Jork (USA)</option>
                </select>
                <button type="submit" style="padding: 5px 10px; font-size: 16px;">Sprawdź pogodę</button>
            </form>
        </body></html>
        """
        self.wfile.write(html.encode('utf-8'))

    def do_POST(self):
        # Odczytanie danych z formularza
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = parse_qs(post_data)
        
        city = parsed_data.get('city', [''])[0]
        
        if city in CITIES:
            lat, lon = CITIES[city]
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            try:
                # Dodanie nagłówka User-Agent, niektóre API blokują domyślnego klienta Pythona
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                    temp = data['current_weather']['temperature']
                    wind = data['current_weather']['windspeed']
                    
                    html = f'''
                    <html><head><title>Wynik pogody</title><meta charset="utf-8"></head>
                    <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                        <h2>Aktualna pogoda dla: {city}</h2>
                        <p style="font-size: 18px;"><b>Temperatura:</b> {temp} &deg;C</p>
                        <p style="font-size: 18px;"><b>Prędkość wiatru:</b> {wind} km/h</p>
                        <br><br><a href="/" style="text-decoration: none; background: #eee; padding: 10px; border-radius: 5px;">Powrót</a>
                    </body></html>
                    '''
            except Exception as e:
                 html = f"Wystąpił błąd podczas pobierania danych: {str(e)}"
        else:
            html = "Nieznane miasto"
            
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

if __name__ == "__main__":
    # Realizacja wymogu 1a (logowanie do konsoli przy starcie)
    startup_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=== START APLIKACJI ===")
    print(f"Data uruchomienia: {startup_date}")
    print(f"Autor programu: {AUTHOR}")
    print(f"Aplikacja nasłuchuje na porcie TCP: {PORT}")
    
    # Serwer działa do momentu ręcznego przerwania
    with socketserver.TCPServer(("0.0.0.0", PORT), WeatherHandler) as httpd:
        httpd.serve_forever()
```

## 2. Plik Dockerfile
Plik został zoptymalizowany pod kątem bezpieczeństwa (użytkownik non-root) oraz zrealizowano w nim mechanizm wieloetapowego budowania. Kopiując system plików bezpośrednio z etapu budowy (alpine) do warstwy scratch, uzyskano minimalny obraz docelowy osadzony w pustej warstwie.
**Plik `Dockerfile`:**
```
# --- ETAP 1: Obraz bazowy ---
FROM python:3.12-alpine AS builder

WORKDIR /app
COPY main.py .

# Optymalizacja: Kompilacja do bytecode'u
RUN python -m compileall main.py

# Tworzenie użytkownika non-root
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app

# --- ETAP 2: Docelowy obraz ---
FROM scratch

# Wymóg: Etykiety OCI
LABEL org.opencontainers.image.authors="Jan Krzemiński" \
      org.opencontainers.image.title="Cloud Weather App (Python w Scratch)" \
      org.opencontainers.image.description="Aplikacja do sprawdzania pogody"

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Kopiujemy fizyczny system plików z etapu "builder" do warstwy scratch
COPY --from=builder / /

# Przełączamy na utworzonego wcześniej użytkownika bez uprawnień roota
USER appuser

EXPOSE 8080

# Healthcheck bazujący na wbudowanym narzędziu wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health || exit 1

# Uruchomienie aplikacji w Pythonie wewnątrz warstwy scratch
CMD ["python", "main.py"]
```

## 3. Wykorzystane polecenia
**a) Budowanie obrazu kontenera:**
```
docker build -t lab-weather-python:v1 .
```
**b) Uruchomienie kontenera:**
```
docker run -d -p 8080:8080 --name weather-app lab-weather-python:v1
```
**c) Sprawdzenie logów wygenerowanych przez aplikację:**
```
docker logs weather-app
```
<img width="601" height="352" alt="obraz" src="https://github.com/user-attachments/assets/dd4a7865-24b7-4d32-bed3-f12407fb1379" />

**d) Sprawdzenie rozmiaru oraz ilości warstw obrazu:**
```
docker images lab-weather-python:v1
docker history lab-weather-python:v1
```
<img width="895" height="371" alt="obraz" src="https://github.com/user-attachments/assets/995cd15d-687c-4555-a09c-4bf3c1f2e031" />

## 4. Weryfikacja działania aplikacji
Poniżej znajduje się zrzut ekranu z poprawnie działającej aplikacji udostępniającej GUI i pobierającej aktualną pogodę.
<img width="540" height="261" alt="obraz" src="https://github.com/user-attachments/assets/3c11a777-a151-49cf-9e97-c87f57b631e5" />

<img width="544" height="269" alt="obraz" src="https://github.com/user-attachments/assets/bf9c7621-2e6d-43e4-be08-b61abe77ddd9" />




