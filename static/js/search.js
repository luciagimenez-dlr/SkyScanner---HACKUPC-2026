/**
 * search.js — Lògica de la pàgina de Cerca / Planificador AI
 * ============================================================
 * Gestiona:
 *  - Xat amb Gemini AI (multi-torn)
 *  - Renderització de l'itinerari
 *  - Mapa Leaflet amb marcadors de parades
 *  - Vídeos VR de la comunitat
 *  - Quick chips de context
 */

// ============================================================
// ESTAT GLOBAL DE LA PÀGINA
// ============================================================
let conversationHistory = []; // Historial complet del xat per mantenir context
let map = null;               // Instància del mapa Leaflet
let markers = [];             // Marcadors actius al mapa

// ============================================================
// INICIALITZACIÓ
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  setupChat();
  setupQuickChips();
});

// ============================================================
// XAT: setup i enviament de missatges
// ============================================================
function setupChat() {
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("chatSendBtn");

  if (!input || !sendBtn) return;

  // Enviar amb el botó
  sendBtn.addEventListener("click", sendMessage);

  // Enviar amb Enter (Shift+Enter = nova línia)
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize del textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });
}

/**
 * Envia el missatge de l'usuari a la IA i processa la resposta.
 */
async function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;

  // Mostra el missatge de l'usuari al xat
  appendMessage("user", message);
  input.value = "";
  input.style.height = "auto";

  // Mostra el loader
  showLoader(true);

  // Recull les preferències avançades
  const preferences = {
    budget: document.getElementById("prefBudget")?.value || "",
    transport_preferences: getSelectedTags("transportSelector"),
    accommodation_priority: document.getElementById("prefAccom")?.value || "centre",
  };

  // Construeix el payload per a l'API
  const payload = {
    message,
    conversation_history: conversationHistory,
    ...preferences,
  };

  // Crida a l'API Flask → search_bp.py
  const result = await apiPost("/search/plan", payload);

  showLoader(false);

  if (!result) {
    appendMessage("ai", "Ho sento, hi ha hagut un error. Torna-ho a intentar.");
    return;
  }

  // Afegeix la interacció a l'historial
  conversationHistory.push({ role: "user", content: message });

  if (result.type === "structured_plan") {
    // Resposta estructurada → renderitza l'itinerari complet
    const plan = result.plan;

    // Missatge de confirmació al xat
    appendMessage(
      "ai",
      `He creat el teu itinerari per a ${plan.destination}! 🗺️ Mira el resultat a la dreta.`
    );
    conversationHistory.push({
      role: "assistant",
      content: `He creat l'itinerari per ${plan.destination}`,
    });

    // Renderitza tots els components visuals
    renderItinerary(plan);
    renderMap(plan);
    loadVRVideos(plan.destination);

  } else {
    // Conversa normal → mostra la resposta de text
    appendMessage("ai", result.message);
    conversationHistory.push({ role: "assistant", content: result.message });
  }
}

// ============================================================
// XAT: helpers de renderització
// ============================================================

/**
 * Afegeix un missatge nou al panell de xat.
 * @param {"ai"|"user"} role
 * @param {string} text
 */
function appendMessage(role, text) {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const div = document.createElement("div");
  div.className = `chat-message chat-message--${role}`;
  div.innerHTML = `
    <div class="chat-message__bubble">
      ${escapeHtml(text).replace(/\n/g, "<br>")}
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight; // Scroll al final
}

function showLoader(visible) {
  const loader = document.getElementById("aiLoader");
  if (loader) loader.style.display = visible ? "flex" : "none";
}

// ============================================================
// QUICK CHIPS
// ============================================================
function setupQuickChips() {
  const chips = document.querySelectorAll(".chip");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const input = document.getElementById("chatInput");
      if (input) {
        // Afegeix el text del chip a l'input
        input.value += (input.value ? " " : "") + chip.dataset.text;
        input.focus();
      }
    });
  });
}

// ============================================================
// ITINERARI: renderitza l'estructura de dies i parades
// ============================================================
function renderItinerary(plan) {
  // Amaga l'estat buit, mostra l'itinerari
  const empty = document.getElementById("resultsEmpty");
  const itinerary = document.getElementById("itinerary");
  if (empty) empty.style.display = "none";
  if (itinerary) itinerary.style.display = "block";

  // Títol i resum
  const title = document.getElementById("itineraryTitle");
  const summary = document.getElementById("itinerarySummary");
  if (title) title.textContent = plan.destination || "El teu viatge";
  if (summary) summary.textContent = plan.trip_summary || "";

  // Notes culturals
  renderCulturalNotes(plan.cultural_notes, plan.sustainability_tips);

  // Dies
  const daysList = document.getElementById("daysList");
  if (daysList && plan.days) {
    daysList.innerHTML = plan.days.map(renderDay).join("");

    // Afegeix click als stops per centrar el mapa
    daysList.querySelectorAll(".stop-item").forEach((stopEl) => {
      stopEl.addEventListener("click", () => {
        const lat = parseFloat(stopEl.dataset.lat);
        const lng = parseFloat(stopEl.dataset.lng);
        if (map && !isNaN(lat) && !isNaN(lng)) {
          map.setView([lat, lng], 15, { animate: true });
        }
      });
    });
  }

  // Pressupost
  renderBudget(plan.budget_breakdown);
}

function renderCulturalNotes(culturalNotes, sustainabilityTips) {
  const section = document.getElementById("culturalNotes");
  const list = document.getElementById("culturalNotesList");
  if (!section || !list) return;

  const allNotes = [
    ...(culturalNotes || []),
    ...(sustainabilityTips || [])
  ];

  if (allNotes.length === 0) return;

  list.innerHTML = allNotes.map((n) => `<li>${escapeHtml(n)}</li>`).join("");
  section.style.display = "block";
}

function renderDay(day) {
  const stopsHtml = (day.stops || []).map(renderStop).join("");
  return `
    <div class="day-card">
      <div class="day-card__header">
        <span class="day-card__number">Dia ${day.day}</span>
        <span class="day-card__theme">${escapeHtml(day.theme || "")}</span>
      </div>
      <div class="stops-list">${stopsHtml}</div>
    </div>
  `;
}

function renderStop(stop) {
  const typeEmoji = {
    museu: "🖼️", restaurant: "🍽️", monument: "🏛️",
    parc: "🌿", fotos: "📸", descans: "☕", hotel: "🏨"
  };
  const emoji = typeEmoji[stop.type] || "📍";

  return `
    <div class="stop-item"
         data-lat="${stop.lat || ""}"
         data-lng="${stop.lng || ""}">
      <span class="stop-item__time">${stop.time || ""}</span>
      <div class="stop-item__info">
        <div class="stop-item__name">${emoji} ${escapeHtml(stop.name || "")}</div>
        <div class="stop-item__desc">${escapeHtml(stop.description || "")}</div>
        <div class="stop-item__meta">
          ${stop.duration_minutes ? `<span class="stop-meta-tag">⏱ ${stop.duration_minutes}min</span>` : ""}
          ${stop.price_estimate ? `<span class="stop-meta-tag">${stop.price_estimate}</span>` : ""}
          ${stop.accessibility ? `<span class="stop-meta-tag">♿ ${escapeHtml(stop.accessibility)}</span>` : ""}
          ${stop.instagram_tip ? `<span class="stop-meta-tag">📸 Foto</span>` : ""}
        </div>
      </div>
    </div>
  `;
}

function renderBudget(breakdown) {
  const section = document.getElementById("budgetSummary");
  const grid = document.getElementById("budgetGrid");
  if (!section || !grid || !breakdown) return;

  const labels = {
    accommodation: "Allotjament",
    food_per_day: "Menjar/dia",
    activities: "Activitats",
    transport: "Transport"
  };

  grid.innerHTML = Object.entries(breakdown)
    .map(([key, value]) => `
      <div class="budget-item">
        <span class="budget-item__label">${labels[key] || key}</span>
        <span class="budget-item__value">${escapeHtml(String(value))}</span>
      </div>
    `).join("");

  section.style.display = "block";
}

// ============================================================
// MAPA LEAFLET
// ============================================================

/**
 * Inicialitza o actualitza el mapa amb els punts de l'itinerari.
 * Usa OpenStreetMap (gratuït, sense clau API).
 */
function renderMap(plan) {
  const mapContainer = document.getElementById("mapContainer");
  const mapEl = document.getElementById("map");
  if (!mapContainer || !mapEl) return;

  // Recull tots els stops amb coordenades
  const stops = [];
  (plan.days || []).forEach((day) => {
    (day.stops || []).forEach((stop) => {
      if (stop.lat && stop.lng) {
        stops.push({ ...stop, day: day.day });
      }
    });
  });

  if (stops.length === 0) return;

  mapContainer.style.display = "block";

  // Inicialitza Leaflet (o neteja el mapa existent)
  if (map) {
    map.remove();
    markers = [];
  }

  // Centre del mapa = primer stop
  map = L.map("map").setView([stops[0].lat, stops[0].lng], 13);

  // Tiles d'OpenStreetMap
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);

  // Afegeix marcadors per cada stop
  stops.forEach((stop, index) => {
    // Icona personalitzada amb número
    const icon = L.divIcon({
      className: "",
      html: `
        <div style="
          background: #c8a96e;
          color: #0d0d0e;
          border-radius: 50%;
          width: 28px; height: 28px;
          display: flex; align-items: center; justify-content: center;
          font-weight: 700; font-size: 11px;
          border: 2px solid #fff;
          box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        ">${index + 1}</div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });

    const marker = L.marker([stop.lat, stop.lng], { icon })
      .addTo(map)
      .bindPopup(`
        <strong>${stop.name}</strong><br>
        ${stop.time ? `🕐 ${stop.time}<br>` : ""}
        ${stop.description || ""}
        ${stop.price_estimate ? `<br>💰 ${stop.price_estimate}` : ""}
      `);

    markers.push(marker);
  });

  // Ajusta la vista per mostrar tots els marcadors
  if (stops.length > 1) {
    const bounds = L.latLngBounds(stops.map((s) => [s.lat, s.lng]));
    map.fitBounds(bounds, { padding: [30, 30] });
  }

  // Dibuixa ruta entre stops (línia simple)
  const latlngs = stops.map((s) => [s.lat, s.lng]);
  L.polyline(latlngs, {
    color: "#c8a96e",
    weight: 2,
    opacity: 0.6,
    dashArray: "6, 8",
  }).addTo(map);
}

// ============================================================
// VÍDEOS VR DE LA COMUNITAT
// ============================================================

/**
 * Carrega els vídeos VR pujats per la comunitat per a la destinació.
 */
async function loadVRVideos(destination) {
  const city = destination ? destination.split(",")[0].trim() : "";
  const data = await apiGet(`/api/map-points?city=${encodeURIComponent(city)}`);

  // Cridada específica per VR
  const videos = await apiGet(`/search/vr-videos?city=${encodeURIComponent(city.toLowerCase())}`);

  const section = document.getElementById("vrPreview");
  const grid = document.getElementById("vrGrid");
  if (!section || !grid) return;

  if (!videos || videos.length === 0) return; // No hi ha vídeos, no mostrem la secció

  section.style.display = "block";
  grid.innerHTML = videos
    .map(
      (v) => `
    <div class="vr-card" onclick="openVRVideo('${escapeHtml(v.vr_url || "")}')">
      <div class="vr-card__thumb">▶</div>
      <div class="vr-card__info">
        <div class="vr-card__title">${escapeHtml(v.title || "Vídeo VR")}</div>
        <div class="vr-card__meta">Per ${escapeHtml(v.uploader || "Anònim")} · Obre en VR</div>
      </div>
    </div>
  `
    )
    .join("");
}

/**
 * Obre el vídeo VR en una nova pestanya per ser reproduït amb les ulleres.
 */
function openVRVideo(url) {
  if (!url) return;
  window.open(url, "_blank");
}

// ============================================================
// UTILS
// ============================================================

/** Escapa HTML per evitar XSS */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(String(text)));
  return div.innerHTML;
}
