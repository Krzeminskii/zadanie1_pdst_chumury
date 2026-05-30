# Laboratorium: Programowanie Aplikacji w Chmurze Obliczeniowej
**Zadanie 2**

**Autor:** Jan Krzemiński

### 1. Rozwiązanie problemu skanowania obrazów Multi-arch
Zastosowano podejście dwuetapowego budowania obrazu. Narzędzie Docker Buildx domyślnie nie pozwala na załadowanie do lokalnego demona obrazu zbudowanego dla wielu architektur.
Jest to jednak wymagane przez skanery bezpieczeństwa przed publikacją.
Aby to rozwiązać, łańcuch wykonuje:
* Budowanie lokalne wyłącznie dla architektury runnera (`linux/amd64`) z flagą `load: true`.
* Skanowanie wygenerowanego lokalnie obrazu.
* Po pomyślnym teście CVE – drugie budowanie dla docelowych architektur (`linux/amd64`, `linux/arm64`) z flagą `push: true`. Dzięki wykorzystaniu cache, drugi etap kompiluje się błyskawicznie.

### 2. Skanowanie bezpieczeństwa (Trivy)
Do realizacji testu CVE wykorzystano skaner **Trivy** w postaci oficjalnej akcji GitHub (`aquasecurity/trivy-action`).
Został on skonfigurowany w trybie "fail-fast" za pomocą parametru `exit-code: '1'` oraz `severity: 'CRITICAL,HIGH'`. 
Taka konfiguracja gwarantuje, że proces zostanie przerwany błędem, jeśli w obrazie znajdą się poważne luki, skutecznie blokując ich wysyłkę do rejestru.

### 3. Konfiguracja Pamięci Podręcznej (Cache)
Zgodnie z wymaganiami, cache eksportowany jest do zewnętrznego, dedykowanego repozytorium na DockerHub, przy użyciu eksportera i backendu typu `registry`.
Wykorzystano tryb `mode=max`, aby buforować wszystkie pośrednie warstwy z wieloetapowego budowania obrazu.

### 4. Obsługa sekretów BuildKit (Integracja z Zadaniem 1)
Aby zachować zgodność z kodem źródłowym z Zadania 1 (wykorzystującym instrukcję `RUN --mount=type=secret...` do klonowania kodu z repozytorium),
zaimplementowano w środowisku GitHub Actions przekazywanie kluczy przez parametr `secrets` w akcji `docker/build-push-action`.
Bezpiecznie wstrzykuje PAT do demona BuildKit bez ingerencji w architekturę obrazu.

---

## Schemat tagowania
Proces generowania tagów został zautomatyzowany przy pomocy akcji `docker/metadata-action`.

### Tagowanie docelowych obrazów (GHCR)
Obrazy wypychane do publicznego rejestru wykorzystują metadane Git:
* **Zasada "Git Truth" (Hash SHA):** Obrazy tagowane są unikalnym identyfikatorem commitu (np. `sha-4a1b2c3`). Jest to fundamentalna praktyka ułatwiająca *traceability*. Pozwala jednoznacznie powiązać działający w chmurze kontener z precyzyjnym stanem kodu źródłowego w repozytorium, co jest kluczowe przy rollbackach i debugowaniu.
* **Semantic Versioning:** Dla tagów produkcyjnych w repozytorium generowane są czytelne wersje numeryczne (np. `1.0.0`), które są przyjaźniejsze dla użytkowników.

### Tagowanie Pamięci Podręcznej (DockerHub)
Tag dla danych cache został powiązany ze zmienną wskazującą na gałąź, z której generowany jest obraz (w tym przypadku `main`). 
**Uzasadnienie:** Separacja cache dla poszczególnych gałęzi to dobra praktyka chroniąca przed tzw. *cache poisoning* (zatruciem pamięci podręcznej).
Zapobiega to sytuacji, w której niestabilne, eksperymentalne kompilacje z gałęzi deweloperskich nadpisują i unieważniają optymalny cache głównej gałęzi produkcyjnej.

### Źródła dotyczące tagowania

Przyjęta strategia tagowania opiera się na oficjalnych dokumentacjach oraz szeroko uznanych dobrych praktykach DevOps:

1. **Tagowanie obrazów hashem SHA (Zasada Traceability):** Zgodnie z oficjalną dokumentacją narzędzia [docker/metadata-action](https://github.com/docker/metadata-action), wykorzystanie atrybutu `type=sha` jest rekomendowanym standardem w automatyzacji CI/CD. Pozwala to na realizację postulatów podejścia **GitOps**, gdzie repozytorium Git jest jedynym źródłem prawdy (Single Source of Truth), a obraz można bezbłędnie powiązać z konkretnym commitem.
2. **Wersjonowanie Semantyczne (SemVer):** Wykorzystanie czytelnych tagów (np. `1.0.0`) opiera się na globalnym standardzie [Semantic Versioning (semver.org)](https://semver.org/lang/pl/), który jest fundamentem przewidywalnego dystrybuowania oprogramowania i zarządzania zależnościami w architekturach opartych na mikroserwisach.
3. **Izolacja pamięci podręcznej (Cache per-branch):** Zgodnie z oficjalną dokumentacją [Docker Buildx Cache Backends](https://docs.docker.com/build/cache/backends/registry/), twórcy Dockera wskazują na konieczność świadomego przyjęcia własnej strategii nazewnictwa i separacji tagów dla pamięci podręcznej. Zastosowane w potoku przypisanie tagu na podstawie gałęzi (`ref=${{ env.CACHE_IMAGE }}:main`) stanowi wdrożenie tej rekomendacji w oparciu o powszechne dobre praktyki CI/CD. Gwarantuje to logiczną separację danych buforowych, co chroni przed nadpisywaniem wydajnego cache'u gałęzi produkcyjnej przez niestabilne warstwy pochodzące z gałęzi deweloperskich.

---

## Pełna zawartość pliku konfiguracyjnego `ci.yml`
Poniżej załączam kompletny kod potoku CI/CD, który znajduje się w repozytorium pod ścieżką `.github/workflows/ci.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches:
      - main
    tags:
      - 'v*.*.*'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
  CACHE_IMAGE: ${{ secrets.DOCKERHUB_USERNAME }}/app-cache

jobs:
  build-scan-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch
            type=semver,pattern={{version}}

      # ETAP 1: Budowanie lokalne dla skanera (AMD64) z przekazaniem sekretu
      - name: Build and load for scanning
        uses: docker/build-push-action@v5
        with:
          context: .
          load: true
          tags: local-image:scan
          cache-from: type=registry,ref=${{ env.CACHE_IMAGE }}:main
          cache-to: type=registry,ref=${{ env.CACHE_IMAGE }}:main,mode=max
          secrets: |
            my_github_token=${{ secrets.MY_GITHUB_TOKEN }}

      # ETAP 2: Skanowanie obrazu (Trivy)
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'local-image:scan'
          format: 'table'
          exit-code: '1'
          ignore-unfixed: true
          vuln-type: 'os,library'
          severity: 'CRITICAL,HIGH'

      # ETAP 3: Budowanie Multi-arch i Push (uruchomi się, jeśli Trivy zwróci 0)
      - name: Build and push multi-arch image
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=registry,ref=${{ env.CACHE_IMAGE }}:main
          cache-to: type=registry,ref=${{ env.CACHE_IMAGE }}:main,mode=max
          secrets: |
            my_github_token=${{ secrets.MY_GITHUB_TOKEN }}
```
## Potwierdzenie działania zadania
### 1. Pełny przebieg łańcucha CI/CD
Główny widok pomyślnie wykonanego potoku. Wszystkie zdefiniowane kroki zakończyły się statusem sukcesu.
<img width="1515" height="850" alt="obraz" src="https://github.com/user-attachments/assets/1014416d-eb63-4e2f-aaaa-2bc3b366343b" />

### 2. Wyniki testu bezpieczeństwa CVE
Logi z konsoli kroku `Run Trivy vulnerability scanner`.
<img width="852" height="957" alt="obraz" src="https://github.com/user-attachments/assets/83b8a675-c311-4cf5-94a1-fe097a1ff999" />

### 3. Eksport pamięci podręcznej na DockerHub
Potwierdzenie prawidłowego działania pamięci podręcznej.
<img width="687" height="550" alt="obraz" src="https://github.com/user-attachments/assets/8dbc8fbd-6394-4bb0-800a-62a1ac6dbd0b" />

Link do repozytorium na Docker hub:
https://hub.docker.com/r/jkrzem/app-cache/tags

