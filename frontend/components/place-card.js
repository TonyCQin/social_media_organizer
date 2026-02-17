// Place Card component — a reusable UI element for displaying a single place

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

export { createPlaceCard };
