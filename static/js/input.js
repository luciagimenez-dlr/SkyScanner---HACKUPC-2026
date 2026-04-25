/**
 * input.js — Lògica de la pàgina d'Input
 * ========================================
 * Gestiona:
 *  - Formulari de perfil d'usuari
 *  - Afegir/eliminar targetes d'experiència
 *  - Rating amb estrelles
 *  - Upload de vídeo i conversió VR
 *  - Sistema de punts
 *  - Leaderboard
 */

// ============================================================
// INICIALITZACIÓ
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  loadPointsBar();    // Carrega punts des del servidor
  loadLeaderboard();  // Carrega el rànquing
  setupExperienceForm();
  setupVRUpload();
  setupSaveButton();
});

// ============================================================
// PUNTS: carrega l'estat actual des del servidor
// ============================================================
async function loadPointsBar() {
  const data = await apiGet("/input/my-points");
  if (data) {
    updatePointsBar(data.points, data.points_for_discount);
  }
}

// ============================================================
// LEADERBOARD: carrega la classificació
// ============================================================
async function loadLeaderboard() {
  const data = await apiGet("/input/leaderboard");
  const list = document.getElementById("leaderboardList");
  if (!list) return;

  if (!data || data.length === 0) {
    list.innerHTML = '<p class="leaderboard__loading">Sense dades</p>';
    return;
  }

  list.innerHTML = data
    .map(
      (user) => `
    <div class="leaderboard-item">
      <span class="leaderboard-item__rank">#${user.rank}</span>
      <span class="leaderboard-item__name">${user.name}</span>
      <span class="leaderboard-item__pts">${user.points}pts</span>
    </div>
  `
    )
    .join("");
}

// ============================================================
// EXPERIÈNCIES: afegir targetes dinàmicament
// ============================================================
function setupExperienceForm() {
  const addBtn = document.getElementById("addExperienceBtn");
  const template = document.getElementById("experienceTemplate");
  const list = document.getElementById("experiencesList");

  if (!addBtn || !template || !list) return;

  // Afegeix una targeta d'experiència en clicar
  addBtn.addEventListener("click", () => {
    const clone = template.content.cloneNode(true);

    // Configura les estrelles de valoració
    const stars = clone.querySelectorAll(".star");
    setupStarRating(stars);

    list.appendChild(clone);
  });
}

/**
 * Configura el comportament de les estrelles de valoració.
 * @param {NodeList} stars - Llista d'estrelles
 */
function setupStarRating(stars) {
  stars.forEach((star) => {
    // Hover: il·lumina fins l'estrella hover
    star.addEventListener("mouseenter", () => {
      const value = parseInt(star.dataset.value);
      stars.forEach((s) => {
        s.classList.toggle("active", parseInt(s.dataset.value) <= value);
      });
    });

    // Click: fixa la valoració
    star.addEventListener("click", () => {
      const value = parseInt(star.dataset.value);
      const ratingContainer = star.closest(".star-rating");
      ratingContainer.dataset.rating = value;
      stars.forEach((s) => {
        s.classList.toggle("active", parseInt(s.dataset.value) <= value);
      });
    });

    // Mouse leave: torna a l'estat fixat
    star.addEventListener("mouseleave", () => {
      const ratingContainer = star.closest(".star-rating");
      const fixedRating = parseInt(ratingContainer.dataset.rating || 0);
      stars.forEach((s) => {
        s.classList.toggle("active", parseInt(s.dataset.value) <= fixedRating);
      });
    });
  });
}

// ============================================================
// VR UPLOAD: drag & drop + conversió
// ============================================================
function setupVRUpload() {
  const dropZone = document.getElementById("vrDropZone");
  const fileInput = document.getElementById("vrVideoInput");
  const metadataFields = document.getElementById("vrMetadataFields");
  const progress = document.getElementById("vrProgress");

  if (!dropZone || !fileInput) return;

  // Click a la zona → obre el selector de fitxers
  dropZone.addEventListener("click", () => fileInput.click());

  // Drag & Drop visual
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
  });
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("video/")) {
      handleVideoSelected(file);
    }
  });

  // Selecció via input
  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) handleVideoSelected(file);
  });

  // Mostra camps de metadades quan hi ha vídeo
  function handleVideoSelected(file) {
    dropZone.querySelector(".vr-upload-zone__text").textContent =
      `✅ ${file.name}`;
    dropZone.querySelector(".vr-upload-zone__subtext").textContent =
      `${(file.size / 1024 / 1024).toFixed(1)} MB · Preparat per pujar`;
    if (metadataFields) metadataFields.style.display = "grid";
  }
}

/**
 * Puja el vídeo al servidor per ser convertit a format VR.
 * S'anomena des de saveProfile() quan hi ha vídeo seleccionat.
 */
async function uploadVRVideo() {
  const fileInput = document.getElementById("vrVideoInput");
  const city = document.getElementById("vrCity")?.value || "";
  const desc = document.getElementById("vrDesc")?.value || "";
  const progress = document.getElementById("vrProgress");
  const progressFill = document.getElementById("vrProgressFill");

  if (!fileInput?.files[0]) return null; // No hi ha vídeo, no cal pujar res

  if (progress) progress.style.display = "flex";

  const formData = new FormData();
  formData.append("video", fileInput.files[0]);
  formData.append("city", city);
  formData.append("description", desc);

  try {
    const response = await fetch("/input/upload-video", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (progress) progress.style.display = "none";
    return data;
  } catch (err) {
    console.error("Error pujant vídeo VR:", err);
    if (progress) progress.style.display = "none";
    return null;
  }
}

// ============================================================
// DESA EL PERFIL COMPLET
// ============================================================
function setupSaveButton() {
  const saveBtn = document.getElementById("saveProfileBtn");
  if (!saveBtn) return;

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    saveBtn.textContent = "Desant…";

    // Recull les dades del formulari
    const profileData = {
      name: document.getElementById("userName")?.value || "",
      travel_types: getSelectedTags("travelTypeSelector"),
      accessibility_needs: getSelectedTags("accessibilitySelector"),
      past_experiences: collectExperiences(),
    };

    // 1. Desa el perfil
    const profileResult = await apiPost("/input/profile", profileData);

    // 2. Puja el vídeo VR (si n'hi ha un)
    const vrResult = await uploadVRVideo();

    // Calcula punts totals guanyats
    let totalPointsEarned = 0;
    let messages = [];

    if (profileResult?.success) {
      totalPointsEarned += profileResult.points_earned;
      messages.push(`Perfil desat`);
    }
    if (vrResult?.success) {
      totalPointsEarned += vrResult.points_earned;
      messages.push(`Vídeo VR pujat`);
    }

    // Mostra el toast i actualitza la barra
    if (totalPointsEarned > 0) {
      showPointsToast(messages.join(" · "), totalPointsEarned);
      const newTotal = (profileResult || vrResult)?.total_points || 0;
      updatePointsBar(newTotal, 100);

      // Si ha aconseguit el descompte
      if (profileResult?.discount_unlocked || vrResult?.discount_unlocked) {
        setTimeout(() => {
          alert(
            "🎉 Felicitats! Has aconseguit 100 punts.\nEl teu descompte en el proper vol/hotel és disponible!"
          );
        }, 1000);
      }
    }

    // Recarrega el leaderboard
    loadLeaderboard();

    saveBtn.disabled = false;
    saveBtn.textContent = "Desar i guanyar punts";
  });
}

/**
 * Recull totes les experiències de les targetes del formulari.
 */
function collectExperiences() {
  const cards = document.querySelectorAll(".experience-card");
  return [...cards].map((card) => ({
    city: card.querySelector(".exp-city")?.value || "",
    positive: card.querySelector(".exp-positive")?.value || "",
    negative: card.querySelector(".exp-negative")?.value || "",
    rating: parseInt(card.querySelector(".star-rating")?.dataset.rating || 0),
  }));
}
