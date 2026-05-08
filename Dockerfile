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