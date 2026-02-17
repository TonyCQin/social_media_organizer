// Main entry point — load and render components

// Import components (vanilla JS requires manual script loading, so we'll use simple globals)
// In a real framework, you'd use import statements

(async function init() {
  // Wait for API utility to be loaded (simple wait)
  let apiReady = false;
  let maxAttempts = 10;
  while (!window.fetchLocations && maxAttempts-- > 0) {
    await new Promise(r => setTimeout(r, 100));
  }

  if (!window.fetchLocations) {
    console.error('API utilities not loaded');
    return;
  }

  // Fetch and render places
  const places = await fetchLocations();
  const placesContainer = document.getElementById('places-container');
  const statsContainer = document.getElementById('stats-container');

  if (places.length === 0) {
    placesContainer.innerHTML = '<p>No places ingested yet.</p>';
  } else {
    placesContainer.innerHTML = '';
    places.forEach(place => {
      const card = createPlaceCard(place);
      placesContainer.appendChild(card);
    });
  }

  // Render stats
  const statsPanel = createStatsPanel(places);
  statsContainer.innerHTML = '';
  statsContainer.appendChild(statsPanel);
})();

// Simple component creation functions (until framework is added)
function createPlaceCard(place) {
  const card = document.createElement('div');
  card.className = 'place-card';
  card.innerHTML = `
    <h3>${place.detected_name || 'Unknown Place'}</h3>
    <p class="category"><strong>Category:</strong> ${place.category || 'uncategorized'}</p>
    <p class="caption">${place.caption || '(no caption)'}</p>
    <p class="hashtags">${place.hashtags || '(no hashtags)'}</p>
    <p class="meta">
      <a href="${place.url}" target="_blank">View Source</a>
      ${place.lat && place.lon ? ` | Coordinates: ${place.lat.toFixed(2)}, ${place.lon.toFixed(2)}` : ''}
    </p>
  `;
  return card;
}

function createStatsPanel(places) {
  const categories = {};
  places.forEach(p => {
    const cat = p.category || 'uncategorized';
    categories[cat] = (categories[cat] || 0) + 1;
  });

  const panel = document.createElement('div');
  panel.className = 'stats-panel';
  panel.innerHTML = `
    <div class="stat">
      <h4>Total Places</h4>
      <p class="value">${places.length}</p>
    </div>
    <div class="categories">
      <h4>By Category</h4>
      ${Object.entries(categories).map(([cat, count]) => `
        <div class="category-stat">
          <span>${cat}</span>
          <span class="count">${count}</span>
        </div>
      `).join('')}
    </div>
  `;
  return panel;
}

// API helpers (simple sync version without import)
async function fetchLocations() {
  const API_BASE = 'http://127.0.0.1:8000';
  try {
    const response = await fetch(`${API_BASE}/locations`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error('Error fetching locations:', error);
    return [];
  }
}
