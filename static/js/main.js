/**
 * main.js — Utilitats compartides entre totes les pàgines
 * =========================================================
 */

// ============================================================
// HELPERS D'API
// ============================================================

/**
 * Fa una petició POST a la nostra API Flask.
 * Retorna la resposta en JSON o null en cas d'error.
 */
async function apiPost(endpoint, data) {
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (err) {
    console.error(`Error POST ${endpoint}:`, err);
    return null;
  }
}

/**
 * Fa una petició GET a la nostra API Flask.
 */
async function apiGet(endpoint) {
  try {
    const response = await fetch(endpoint);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (err) {
    console.error(`Error GET ${endpoint}:`, err);
    return null;
  }
}

// ============================================================
// TAG BUTTONS (selectors multi-opció)
// Afegeix comportament als botons .tag-btn de tota la web
// ============================================================
document.querySelectorAll(".tag-selector").forEach((selector) => {
  selector.querySelectorAll(".tag-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.classList.toggle("active");
    });
  });
});

/**
 * Retorna els valors actius d'un selector de tags.
 * @param {string} selectorId - ID del contenidor .tag-selector
 */
function getSelectedTags(selectorId) {
  const container = document.getElementById(selectorId);
  if (!container) return [];
  return [...container.querySelectorAll(".tag-btn.active")].map(
    (btn) => btn.dataset.value
  );
}

// ============================================================
// TOAST DE PUNTS
// Mostra una notificació temporal de punts guanyats
// ============================================================
function showPointsToast(message, points) {
  const toast = document.getElementById("pointsToast");
  const msg = document.getElementById("pointsToastMsg");
  if (!toast || !msg) return;

  msg.textContent = `${message} (+${points} punts)`;
  toast.style.display = "flex";

  // Desapareix als 4 segons
  setTimeout(() => {
    toast.style.display = "none";
  }, 4000);
}

/**
 * Actualitza la barra de progrés de punts al nav.
 */
function updatePointsBar(current, total = 100) {
  const fill = document.getElementById("pointsFill");
  const count = document.getElementById("pointsCount");
  if (!fill || !count) return;

  const pct = Math.min(100, (current / total) * 100);
  fill.style.width = `${pct}%`;
  count.textContent = `${current} / ${total}`;
}

// ============================================================
// ANIMACIÓ D'ENTRADA (scroll reveal)
// ============================================================
const observerOptions = { threshold: 0.1, rootMargin: "0px 0px -50px 0px" };
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = "1";
      entry.target.style.transform = "translateY(0)";
    }
  });
}, observerOptions);

// Aplica l'animació a les seccions de formulari
document.querySelectorAll(".input-section, .feature-card").forEach((el) => {
  el.style.opacity = "0";
  el.style.transform = "translateY(20px)";
  el.style.transition = "opacity 0.5s ease, transform 0.5s ease";
  revealObserver.observe(el);
});
