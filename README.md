# FLota360 — Ficha 360

Dashboard operativo de flota: mantenimiento, telemetría YPF Ruta (Location World) y semáforo de service.

## Cómo correrlo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed_demo.py
uvicorn main:app --host 0.0.0.0 --port 45221
```

En Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python seed_demo.py
uvicorn main:app --host 0.0.0.0 --port 45221
```

Abrí `http://127.0.0.1:45221/` para el tablero, o `http://127.0.0.1:45221/mapa` para ver la flota en el mapa interactivo (Leaflet). Desde el tablero, **Mapa** en el menú o el enlace de cada fila abre la última posición GPS.

## Conectar YPF Ruta

1. Copiá `.env.example` a `.env`.
2. Completá las credenciales de Location World y YPF (las que te dio soporte, no las pegues en el chat):

```
LOCATIONWORLD_CLIENT_ID=
LOCATIONWORLD_CLIENT_SECRET=
YPF_CLIENT_ID=
YPF_CLIENT_SECRET=
YPF_SCOPE=
YPF_USERNAME=
YPF_PASSWORD=
```

3. Reiniciá uvicorn.
4. En el dashboard, usá **Sincronizar YPF Ruta**.

El conector pide el token Auth0 **una sola vez cada 24 h** (lineamiento de Location World) y lo guarda en `.ypf_token_cache.json`. Los llamados a Customer API respetan el rate limit de **2 requests por segundo**.

Después abre la session `3party-jwt` con las credenciales MAG YPF, baja automotores y dispositivos, y guarda última posición y odómetro.

Sin la session MAG, el tablero demo sigue funcionando. No commitees `.env` ni el cache del token.
