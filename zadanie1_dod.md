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

--- 

### Sprawozdanie część dodatkowa

## 1. Analiza podatności na zagrożenia (CVE)
Przed przystąpieniem do budowy obraz został przeskanowany przy użyciu narzędzia Docker Scout. Wykorzystanie obrazu bazowego Alpine, optymalizacja warstw oraz rezygnacja z instalowania zewnętrznych zależności w Pythonie pozwoliła uzyskać najwyższy poziom bezpieczeństwa. 
Obraz nie zawiera ŻADNYCH zagrożeń zakwalifikowanych jako CRITICAL lub HIGH. Drobne podatności na poziomie Medium/Low dotyczą bazowych pakietów Alpine (np. apk) niewykorzystywanych w runtime.
Pełny raport ze skanowania znajduje się w pliku `raport_cve.txt` w niniejszym repozytorium.

## 2. Rozszerzony frontend BuildKit i pobieranie kodu (Mount Secret)
W pliku `Dockerfile` użyto dyrektywy `# syntax=docker/dockerfile:1`, aby aktywować pełnię możliwości BuildKit. Kod aplikacji nie jest kopiowany z dysku lokalnego. Zamiast tego, narzędzie `git` klonuje publiczne repozytorium podczas etapu budowania. Aby autoryzacja przebiegła w pełni bezpiecznie, wykorzystano funkcjonalność `--mount=type=secret`, która wstrzykuje wygenerowany token GitHub (PAT) do zmiennej środowiskowej w kontenerze w momencie uruchomienia `git clone`. Chroni to przed wyciekiem poświadczeń do historii obrazu.

**Zmodyfikowany plik `Dockerfile`:**
```
# syntax=docker/dockerfile:1
# --- ETAP 1: Obraz bazowy (Builder) ---
FROM python:3.12-alpine AS builder

WORKDIR /app

# Wymóg BuildKit: Instalujemy git-a, by pobrać kod z repozytorium
RUN apk add --no-cache git

# Klonowanie kodu prosto z publicznego repozytorium GitHub
# przy wykorzystaniu bezpiecznego przekazywania sekretów (mount secret).
RUN --mount=type=secret,id=my_github_token \
    git clone https://$(cat /run/secrets/my_github_token)@github.com/Krzeminskii/zadanie1_pdst_chumury.git .

RUN python -m compileall main.py

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app

# --- ETAP 2: Obraz docelowy (Scratch) ---
FROM scratch

LABEL org.opencontainers.image.authors="[Twoje Imię i Nazwisko]" \
      org.opencontainers.image.title="Cloud Weather App" \
      org.opencontainers.image.description="Aplikacja pobierana bezpośrednio z GitHuba"

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Skopiowanie systemu z pobraną z GitHuba aplikacją
COPY --from=builder / /

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/health || exit 1

CMD ["python", "main.py"]
```
## 3. Builder, Multi-architektura i Cache w trybie Max
Aby sprostać wymaganiom wieloarchitekturowym oraz cache'owania, utworzono dedykowanego buildera wykorzystującego sterownik `docker-container`:

**Polecenie tworzące buildera:**
`docker buildx create --name cloud-builder --driver docker-container --bootstrap --use`

Następnie zbudowano obraz na platformy `linux/amd64` oraz `linux/arm64`, wykorzystując eksporter rejestru (backend registry) w trybie `max` dla pełnego zapisu warstw pamięci podręcznej.

**Wykorzystane polecenie budujące (zawierające secret, multi-arch i cache):**
`docker buildx build \`
  `--platform linux/amd64,linux/arm64 \`
  `--secret id=my_github_token,src=github_token.txt \`
  `--cache-to type=registry,ref=jkrzem/lab-weather-python:cache,mode=max \`
  `--cache-from type=registry,ref=jkrzem/lab-weather-python:cache \`
  `-t jkrzem/lab-weather-python:v3 \`
  `--push \`
  `.`
Efekt wykorzystanego polecenia

  ```
[+] Building 39.9s (30/30) FINISHED                                docker-container:cloud-builder
 => [internal] load build definition from Dockerfile                                         0.0s
 => => transferring dockerfile: 1.41kB                                                       0.0s
 => resolve image config for docker-image://docker.io/docker/dockerfile:1                    1.8s
 => [auth] docker/dockerfile:pull token for registry-1.docker.io                             0.0s
 => docker-image://docker.io/docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de46944299  3.4s
 => => resolve docker.io/docker/dockerfile:1@sha256:2780b5c3bab67f1f76c781860de469442999ed1  0.0s
 => => sha256:bcb5d2ab7af67a669c932851c8bb8a26895dda6258900edfd7429d57bfd 14.11MB / 14.11MB  3.2s
 => => extracting sha256:bcb5d2ab7af67a669c932851c8bb8a26895dda6258900edfd7429d57bfd3592f    0.2s
 => [linux/arm64 internal] load metadata for docker.io/library/python:3.12-alpine            1.4s
 => [linux/amd64 internal] load metadata for docker.io/library/python:3.12-alpine            1.4s
 => [auth] library/python:pull token for registry-1.docker.io                                0.0s
 => [internal] load .dockerignore                                                            0.0s
 => => transferring context: 2B                                                              0.0s
 => ERROR importing cache manifest from jkrzem/lab-weather-python:cache                      0.7s
 => [linux/arm64 builder 1/7] FROM docker.io/library/python:3.12-alpine@sha256:236173eb7400  4.9s
 => => resolve docker.io/library/python:3.12-alpine@sha256:236173eb74001afe2f60862de935b74f  0.0s
 => => sha256:05b6ee55fad38c6a3dc2ee84c7a44ff2b3429fc3eef0d4c2a2cfeb230b0acd73 250B / 250B   0.3s
 => => sha256:74bec20749987ddac4cc74bd2f826b97908f1c8a71661be8e89e6e8468e 13.89MB / 13.89MB  2.6s
 => => sha256:d17f077ada118cc762df373ff803592abf2dfa3ddafaa7381e364dd27a88f 4.20MB / 4.20MB  3.2s
 => => sha256:3124cc6c064bced8b2c441577d9c793d290258b2eb87477d21572e5a9 457.92kB / 457.92kB  1.1s
 => => extracting sha256:d17f077ada118cc762df373ff803592abf2dfa3ddafaa7381e364dd27a88fca7    0.2s
 => => extracting sha256:3124cc6c064bced8b2c441577d9c793d290258b2eb87477d21572e5a938fb3cb    0.3s
 => => extracting sha256:74bec20749987ddac4cc74bd2f826b97908f1c8a71661be8e89e6e8468e634d9    0.9s
 => => extracting sha256:05b6ee55fad38c6a3dc2ee84c7a44ff2b3429fc3eef0d4c2a2cfeb230b0acd73    0.0s
 => [linux/arm64 stage-1 1/2] WORKDIR /app                                                   0.1s
 => [auth] jkrzem/lab-weather-python:pull token for registry-1.docker.io                     0.0s
 => [linux/amd64 builder 1/7] FROM docker.io/library/python:3.12-alpine@sha256:236173eb7400  6.7s
 => => resolve docker.io/library/python:3.12-alpine@sha256:236173eb74001afe2f60862de935b74f  0.0s
 => => sha256:3a4f2e6e1560fccb75f8aa9c6b7458b3179164f6378b125e533286c88351cd2a 250B / 250B   0.4s
 => => sha256:fd21a26fb55d22baaa317c98a4296e6a284dd39cc0f9e68ef781bb74adf 13.74MB / 13.74MB  5.0s
 => => sha256:254ac41e2afd13e7a1276627191463329b96d835eab35e7804fdad56d 455.66kB / 455.66kB  1.0s
 => => sha256:6a0ac1617861a677b045b7ff88545213ec31c0ff08763195a70a4a5adda57 3.86MB / 3.86MB  2.4s
 => => extracting sha256:6a0ac1617861a677b045b7ff88545213ec31c0ff08763195a70a4a5adda577bb    0.2s
 => => extracting sha256:254ac41e2afd13e7a1276627191463329b96d835eab35e7804fdad56d7e363d5    0.4s
 => => extracting sha256:fd21a26fb55d22baaa317c98a4296e6a284dd39cc0f9e68ef781bb74adfd6dc7    0.8s
 => => extracting sha256:3a4f2e6e1560fccb75f8aa9c6b7458b3179164f6378b125e533286c88351cd2a    0.0s
 => [linux/arm64 builder 2/7] WORKDIR /app                                                   0.2s
 => [linux/arm64 builder 3/7] RUN apk add --no-cache git                                     4.5s
 => [linux/amd64 builder 2/7] WORKDIR /app                                                   0.1s
 => [linux/amd64 builder 3/7] RUN apk add --no-cache git                                     2.6s
 => [linux/amd64 builder 4/7] RUN --mount=type=secret,id=my_github_token     git clone http  0.0s
 => [linux/arm64 builder 4/7] RUN --mount=type=secret,id=my_github_token     git clone http  0.0s
 => [linux/amd64 builder 5/7] RUN python -m compileall main.py                               0.5s
 => [linux/amd64 builder 6/7] RUN addgroup -S appgroup && adduser -S appuser -G appgroup     0.2s
 => [linux/amd64 builder 7/7] RUN chown -R appuser:appgroup /app                             0.3s
 => [linux/arm64 builder 5/7] RUN python -m compileall main.py                               2.4s
 => [linux/amd64 stage-1 2/2] COPY --from=builder / /                                        0.9s
 => [linux/arm64 builder 6/7] RUN addgroup -S appgroup && adduser -S appuser -G appgroup     0.2s
 => [linux/arm64 builder 7/7] RUN chown -R appuser:appgroup /app                             0.3s
 => [linux/arm64 stage-1 2/2] COPY --from=builder / /                                        0.8s
 => exporting to image                                                                      15.2s
 => => exporting layers                                                                      2.4s
 => => exporting manifest sha256:3709fd1cd2e6a4cace4944b49f87bd7d2261206a4af1c854020197af2b  0.0s
 => => exporting config sha256:b1fda2adf89456fd07e6d4bb8ede434132c0dc607954948b2f662cde2237  0.0s
 => => exporting attestation manifest sha256:58fc13e8dbefaeb43846e7403197d1d2ad537d55341fa6  0.0s
 => => exporting manifest sha256:5599b3c8f08c2fe439da44dda271c8dac48bc7781862d2955d11f9875f  0.0s
 => => exporting config sha256:31c527744e71259623696be082f149a8e89be3e6edff828cec2ec6740237  0.0s
 => => exporting attestation manifest sha256:1c66a9379c1c71792d6b0e2d08d05deddacdc07d6721a7  0.0s
 => => exporting manifest list sha256:efc6f0419d51e3de56fa3c89e89ddac261d7a456c7b6d2e3aa363  0.0s
 => => pushing layers                                                                        7.8s
 => => pushing manifest for docker.io/jkrzem/lab-weather-python:v3@sha256:efc6f0419d51e3de5  4.8s
 => exporting cache to registry                                                             17.6s
 => => preparing build cache for export                                                      1.3s
 => => sending cache export                                                                 16.4s
 => => writing layer sha256:3124cc6c064bced8b2c441577d9c793d290258b2eb87477d21572e5a938fb3c  5.6s
 => => writing layer sha256:168485da650810e7953c52075fd5cbff26554ca5fcfda0fb9f77d8f6afd972c  5.2s
 => => writing layer sha256:05b6ee55fad38c6a3dc2ee84c7a44ff2b3429fc3eef0d4c2a2cfeb230b0acd7  4.5s
 => => writing layer sha256:254ac41e2afd13e7a1276627191463329b96d835eab35e7804fdad56d7e363d  3.8s
 => => writing layer sha256:34d51c61084c8b7e5f179defd02aa7f224c6d6901774d7637e0a5374b5a1987  2.0s
 => => writing layer sha256:3a4f2e6e1560fccb75f8aa9c6b7458b3179164f6378b125e533286c88351cd2  1.3s
 => => writing layer sha256:4114d2709060895dbc6a7ec73b968f506434a6fba7393a2d1323973733f4690  1.3s
 => => writing layer sha256:6a0ac1617861a677b045b7ff88545213ec31c0ff08763195a70a4a5adda577b  1.8s
 => => writing layer sha256:74bec20749987ddac4cc74bd2f826b97908f1c8a71661be8e89e6e8468e634d  2.9s
 => => writing layer sha256:975891ef14c74734bb6044e84d4c21b186bd56cce94ac32809b21fc0794ec39  1.7s
 => => writing layer sha256:ab60bfc9c897ce771aa5cc2b334575111650fb934b512f4c63b6e5bf619c874  1.7s
 => => writing layer sha256:b0760d08b5ad9158e9b634c5da3cfb827c386bd8dc1409a4d7d4678091257c0  1.4s
 => => writing layer sha256:b331758734697fc4831d4638d5b8f42f78a7618b538dccbafc7c580093fb61b  1.4s
 => => writing layer sha256:bcb08830535724b968e69bf926da92c0687f23dbd2a81b67d90d249a2000dc7  1.3s
 => => writing layer sha256:c00d7af7bad982cf235eadabe1af39079565c84d9ed330ae9f01321e46df406  0.1s
 => => writing layer sha256:d17f077ada118cc762df373ff803592abf2dfa3ddafaa7381e364dd27a88fca  1.3s
 => => writing layer sha256:d771bac9b24b7ec77b6e41f7eaaec7b1be6934a87ccf14bb5d9e8dc18fe60f8  0.1s
 => => writing layer sha256:dd912e74fac7c6c96d3e620c07f862cdb156445035dd413b94427b1f61f3d6b  4.3s
 => => writing layer sha256:e1661c3f6d3cca1fce5cf74cd2399da5a73f137ed981c651726cfb8b377368f  1.2s
 => => writing layer sha256:e17d6615f2d0a55a1459690813ee85f00ba512ce78444dbf4d6940486890e60  1.1s
 => => writing layer sha256:f1e0905241e605b9a48166ba8f59005315735e6e3db4792c79e7ddd8aa89a3f  0.1s
 => => writing layer sha256:f6ebb04f2f5c80eef9362bbf95b82606e9a372b8916b2071485031f4c05f3f7  1.3s
 => => writing layer sha256:fd21a26fb55d22baaa317c98a4296e6a284dd39cc0f9e68ef781bb74adfd6dc  2.4s
 => => writing config sha256:ba478645af963df25f3e20ca8c988113fb1a763f5dc763f90a62f68b6e2a2f  1.0s
 => => writing cache image manifest sha256:685ae73c60adb28a200efc83305ac1f436b6597a5261c4e3  2.2s
 => [auth] jkrzem/lab-weather-python:pull,push token for registry-1.docker.io                0.0s
------
 > importing cache manifest from jkrzem/lab-weather-python:cache:
------

View build details: docker-desktop://dashboard/build/cloud-builder/cloud-builder0/05pd5s6q61y1agarnpz9da4r4
  ```
Gotowe manifesty wieloarchitekturowe wraz z plikami cache zostały automatycznie wyeksportowane do repozytorium na DockerHubie.



