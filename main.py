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