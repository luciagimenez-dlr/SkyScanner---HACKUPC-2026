# WanderLens 🌍

Plataforma de viatge impulsada per IA per a la Hackathon Skyscanner.

---

## 🚀 Com executar

### 1. Instal·la les dependències
```bash
pip install -r requirements.txt
```

### 2. Configura les claus API
Copia el fitxer d'exemple i edita'l:
```bash
cp .env.example .env
```

Edita `.env` i afegeix les teves claus:
```
GEMINI_API_KEY=AIzaSyD_Inf8KJk09wNE0_xnWL7_5zQCsPWSqRk   ← ja tens aquesta!
SKYSCANNER_API_KEY=la_teva_clau_aqui                       ← obté-la a skyscanner developers
```

**On obtenir la clau Skyscanner:**
→ https://developers.skyscanner.net/docs/intro
→ Registra't → Crea un projecte → Copia l'API Key

### 3. Executa el servidor
```bash
python app.py
```

### 4. Obre el navegador
```
http://localhost:5000
```

---

## 📁 Estructura del projecte

```
wanderlens/
│
├── app.py                    ← Punt d'entrada principal (Flask)
├── requirements.txt          ← Dependències Python
├── .env.example              ← Plantilla de variables d'entorn
│
├── blueprints/               ← Cada fitxer = una part independent
│   ├── __init__.py
│   ├── input_bp.py           ← PART 1: Perfil + Upload VR + Punts
│   ├── search_bp.py          ← PART 2: IA Planner + Itinerari
│   └── api_bp.py             ← PART 3: Skyscanner + Mapes API
│
├── templates/                ← Pàgines HTML
│   ├── index.html            ← Landing page
│   ├── input.html            ← Pàgina d'input / comunitat
│   └── search.html           ← Pàgina de cerca / planificador
│
└── static/
    ├── css/
    │   ├── main.css          ← Estils compartits + Landing
    │   ├── input.css         ← Estils pàgina Input
    │   └── search.css        ← Estils pàgina Search
    └── js/
        ├── main.js           ← Utilitats compartides (fetch, toast...)
        ├── input.js          ← Lògica pàgina Input
        └── search.js         ← Lògica pàgina Search (mapa, xat, IA)
```

---

## 👥 Com dividir la feina

| Persona | Fitxers |
|---------|---------|
| **Dev 1** | `blueprints/input_bp.py` + `templates/input.html` + `static/css/input.css` + `static/js/input.js` |
| **Dev 2** | `blueprints/search_bp.py` + `templates/search.html` + `static/css/search.css` + `static/js/search.js` |
| **Dev 3** | `blueprints/api_bp.py` + `templates/index.html` + `static/css/main.css` |

---

## 🔌 APIs Usades

| API | Ús | Clau necessària? |
|-----|----|-----------------|
| **Gemini AI** (Google) | Planificació de viatge amb IA | ✅ Sí (ja configurada) |
| **Skyscanner** | Cerca de vols | ✅ Sí (registra't a developers.skyscanner.net) |
| **OpenStreetMap / Nominatim** | Geocodificació (coordenades) | ❌ Gratuïta |
| **Overpass API** | Punts d'interès (OSM) | ❌ Gratuïta |
| **Leaflet.js** | Mapes interactius al frontend | ❌ Gratuïta |

---

## 🌍 Agenda 2030

El projecte incorpora:
- **ODS 10** (Reducció de desigualtats): Accessibilitat com a criteri de cerca
- **ODS 12** (Consum responsable): Informació de turisme sostenible generada per IA

---

## 📝 Notes tècniques

- **ffmpeg** és necessari per la conversió de vídeos a format VR.
  Instal·la'l a: https://ffmpeg.org/download.html
- Els vídeos es desen a `static/uploads/videos/`
- El sistema de punts usa sessions Flask (canviar per BD en producció)
