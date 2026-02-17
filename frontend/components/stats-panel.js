// Stats Panel component — displays aggregate counts and categories

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

export { createStatsPanel };
