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
