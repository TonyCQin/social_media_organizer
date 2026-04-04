// Main entry point — load and render components

// Import components (vanilla JS requires manual script loading, so we'll use simple globals)
// In a real framework, you'd use import statements

(async function init() {
  // Wait for API utility to be loaded (simple wait)
  // let apiReady = false;
  // let maxAttempts = 10;
  // while (!window.fetchLocations && maxAttempts-- > 0) {
  //   await new Promise(r => setTimeout(r, 100));
  // }

  // if (!window.fetchLocations) {
  //   console.error('API utilities not loaded');
  //   return;
  // }

  // Fetch and render places
  const places = await fetchLocations();
  const placesContainer = document.getElementById('places-container');
  const statsContainer = document.getElementById('stats-container');

  if (places.length === 0) {
    placesContainer.innerHTML = '<p>No places ingested yet.</p>';
  } else {
    placesContainer.innerHTML = '';
    places.slice(0, 60).forEach(place => {
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

  const caption = place.caption || '(no caption)';
  const shortCaption =
    caption.length > 180 ? caption.slice(0, 180) + '...' : caption;

  const hashtags = place.hashtags
    ? place.hashtags.split('|').join(', ')
    : '(no hashtags)';

  const image = place.display_url || '';
  let locationName = place.location_name || '';
  const captionText = place.caption || '';
  // If location is too generic, try to extract from caption
  if (!locationName || locationName.toLowerCase().includes('atlanta')) {
    const match = captionText.match(/@(\w+)/);
    if (match) {
      locationName = match[1]
        .replace('eat', '')
        .replace(/([A-Z])/g, ' $1')
        .replace(/^./, str => str.toUpperCase())
        .trim();
    }
  }

  // Fallback
  if (!locationName) {
    locationName = 'Unknown Place';
  }
  const permalink = place.permalink || '#';

  card.innerHTML = `
    ${image ? `<img src="${image}" class="place-image" alt="${locationName}" onerror="this.style.display='none'">` : ''}
    <h3>${locationName}</h3>
    <p class="caption">${shortCaption}</p>
    <p class="hashtags"><strong>Hashtags:</strong> ${hashtags}</p>
    <p class="meta">
      <a href="${permalink}" target="_blank" rel="noopener noreferrer">View Post</a>
    </p>
  `;
  return card;
}

function createStatsPanel(places) {
  // const categories = {};
  // places.forEach(p => {
  //   const cat = p.category || 'uncategorized';
  //   categories[cat] = (categories[cat] || 0) + 1;
  // });

  // const panel = document.createElement('div');
  // panel.className = 'stats-panel';
  // panel.innerHTML = `
  //   <div class="stat">
  //     <h4>Total Places</h4>
  //     <p class="value">${places.length}</p>
  //   </div>
  //   <div class="categories">
  //     <h4>By Category</h4>
  //     ${Object.entries(categories).map(([cat, count]) => `
  //       <div class="category-stat">
  //         <span>${cat}</span>
  //         <span class="count">${count}</span>
  //       </div>
  //     `).join('')}
  //   </div>
  // `;
  // return panel;
  const categories = {};

  places.forEach(p => {
    const text = `${p.caption || ''} ${p.hashtags || ''}`.toLowerCase();

    let category = 'other';

    if (text.includes('coffee') || text.includes('cafe')) {
      category = 'coffee';
    } else if (
    text.includes('restaurant') ||
    text.includes('food') ||
    text.includes('eat') ||
    text.includes('brunch') ||
    text.includes('dinner') ||
    text.includes('lunch')
  ) {
      category = 'food';
    } else if (
    text.includes('bar') ||
    text.includes('drink') ||
    text.includes('cocktail') ||
    text.includes('brew')
  ) {
      category = 'bar';
    } else if (text.includes('park') || text.includes('trail') || text.includes('outdoor')) {
      category = 'outdoors';
    } else if (text.includes('shop') || text.includes('store') || text.includes('market')) {
      category = 'shopping';
    }

    categories[category] = (categories[category] || 0) + 1;
  });

  const panel = document.createElement('div');
  panel.className = 'stats-panel';

  panel.innerHTML = `
    <div class="stat">
      <h4>Total Posts</h4>
      <p class="value">${places.length}</p>
    </div>

    <div class="categories">
      <h4>By Category</h4>
      ${Object.entries(categories)
        .map(([cat, count]) => `
          <div class="category-stat">
            <span>${cat}</span>
            <span class="count">${count}</span>
          </div>
        `)
        .join('')}
    </div>
  `;
  return panel;
}

// API helpers (simple sync version without import)
// async function fetchLocations() {
//   const API_BASE = 'http://127.0.0.1:8000';
//   try {
//     const response = await fetch(`${API_BASE}/locations`);
//     if (!response.ok) throw new Error(`HTTP ${response.status}`);
//     return await response.json();
//   } catch (error) {
//     console.error('Error fetching locations:', error);
//     return [];
//   }
// }

// CSV helper for now
async function fetchLocations() {
  try {
    const response = await fetch('./data/instagram_posts.csv');
    const csvText = await response.text();

    const parsed = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true
    });

    return parsed.data;
  } catch (error) {
    console.error('Error fetching locations:', error);
    return [];
  }
}
