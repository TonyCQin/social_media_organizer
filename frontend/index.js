/* APP STARTUP */
(async function init() {
  //Load data
  const places = await fetchLocations();
  places.sort((a, b) => Number(b.confidence) - Number(a.confidence));

  //Constants and initial app state
  const placesContainer = document.getElementById("places-container");
  const statsContainer = document.getElementById("stats-container");
  const filtersContainer = document.getElementById("filters");
  const searchBar = document.getElementById("search-bar");
  let currentCategory = "All";

  //Initial rendering
  renderPlaces(places);
  renderFilters();

  //Search
  searchBar.addEventListener("input", applyFilters);

  //Stats
  const statsPanel = createStatsPanel(places);
  statsContainer.innerHTML = "";
  statsContainer.appendChild(statsPanel);

  //Filtering and rendering functions
  function applyFilters() {
    const searchText = searchBar.value.trim().toLowerCase();

    let filtered = places;

    if (currentCategory === "Favorites") {
      const favs = getFavorites();

      filtered = filtered.filter((p) => favs.includes(p.permalink || "#"));
    } else if (currentCategory !== "All") {
      filtered = filtered.filter(
        (p) => cleanName(p.category || "Misc") === currentCategory,
      );
    }

    filtered = filtered.filter((p) => {
      const name = getBestPlaceName(p).toLowerCase();
      const cuisine = (p.cuisines || "").toLowerCase();

      return name.includes(searchText) || cuisine.includes(searchText);
    });

    renderPlaces(filtered);
  }

  function renderPlaces(data) {
    if (data.length === 0) {
      placesContainer.innerHTML =
        "<p>No matches found. Try another search.</p>";
      return;
    }

    placesContainer.innerHTML = "";

    //Removes duplicate cards if same place mentioned in multiple posts
    const unique = [];
    const seen = new Set();

    data.forEach((place) => {
      const name = getBestPlaceName(place);

      if (!seen.has(name)) {
        seen.add(name);
        unique.push(place);
      }
    });

    unique.slice(0, 60).forEach((place) => {
      placesContainer.appendChild(createPlaceCard(place));
    });
  }

  function renderFilters() {
    const categories = [
      "All",
      "Dinner",
      "Drinks",
      "Brunch",
      "Dessert",
      "Event",
      "Favorites",
    ];

    filtersContainer.innerHTML = "";

    categories.forEach((cat) => {
      const btn = document.createElement("button");
      btn.textContent = cat;
      btn.className = "filter-btn";
      if (cat === "Favorites") {
        btn.classList.add("favorites-filter");
        btn.textContent = "★ Saved";
      }

      btn.onclick = () => {
        document
          .querySelectorAll(".filter-btn")
          .forEach((b) => b.classList.remove("active"));

        btn.classList.add("active");

        currentCategory = cat;
        applyFilters();
      };

      filtersContainer.appendChild(btn);

      if (cat === "All") {
        btn.classList.add("active");
      }
    });
  }
})();

/* READ DATA FROM SQL-GENERATED CSV */
async function fetchLocations() {
  try {
    const response = await fetch("./data/final_post_classifications.csv");
    const csvText = await response.text();

    const parsed = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
    });

    return parsed.data;
  } catch (error) {
    console.error("Error fetching locations:", error);
    return [];
  }
}

/* SAVED PLACES */
function getFavorites() {
  return JSON.parse(localStorage.getItem("favorites") || "[]");
}

function toggleFavorite(id) {
  let favs = getFavorites();

  if (favs.includes(id)) {
    favs = favs.filter((x) => x !== id);
  } else {
    favs.push(id);
  }

  localStorage.setItem("favorites", JSON.stringify(favs));
}

/* CARD RENDERING */
function createPlaceCard(place) {
  const card = document.createElement("div");
  card.className = "place-card";

  const locationName = getBestPlaceName(place);

  const category = place.category || "Misc";

  const cuisines = place.cuisines
    ? place.cuisines.replaceAll("|", ", ")
    : "N/A";

  const type = place.content_type
    ? place.content_type.replaceAll("_", " ")
    : "N/A";

  const confidence = place.confidence
    ? Math.round(Number(place.confidence) * 100) + "%"
    : "N/A";

  const permalink = place.permalink || "#";
  const isFav = getFavorites().includes(permalink);

  card.innerHTML = `
    <div class="card-top">
      <h3>${locationName}</h3>
      <button class="favorite-btn ${isFav ? "favorited" : ""}">
        ${isFav ? "★" : "☆"}
      </button>
    </div>
    <p><strong>Category:</strong> ${cleanName(category)}</p>
    <p><strong>Cuisine:</strong> ${cleanName(cuisines)}</p>
    <p><strong>Type:</strong> ${cleanName(type)}</p>
    <p><strong>Confidence:</strong> ${confidence}</p>
    <p class="meta">
      <a href="${permalink}" target="_blank" rel="noopener noreferrer">
        View Post
      </a>
    </p>
  `;
  card.querySelector(".favorite-btn").onclick = () => {
    toggleFavorite(permalink);
    location.reload();
  };

  return card;
}

/* PLACE NAME DETECTION & CLEANUP */

// Ranks caption mentions by likelihood of being the actual venue
function getBestPlaceName(place) {
  const caption = place.caption || "";
  const owner = (place.owner_username || "").toLowerCase();
  const mentions = [...caption.matchAll(/@([a-zA-Z0-9._]+)/g)]
    .map((m) => m[1])
    .slice(0, 4);

  const blacklist = [owner, "atllovesmo", "vs.thebarkeep", "xuanthia"];

  let bestMention = null;
  let bestScore = Number.NEGATIVE_INFINITY;

  mentions.forEach((name) => {
    const lower = name.toLowerCase();

    if (blacklist.includes(lower)) return;

    let score = 0;

    //Positive signals (business account)
    if (lower.includes("cafe")) score += 3;
    if (lower.includes("coffee")) score += 3;
    if (lower.includes("bar")) score += 3;
    if (lower.includes("grill")) score += 3;
    if (lower.includes("pizza")) score += 3;
    if (lower.includes("kitchen")) score += 3;
    if (lower.includes("garden")) score += 2;
    if (lower.includes("house")) score += 2;
    if (lower.includes("cantina")) score += 2;
    if (lower.includes("restaurant")) score += 3;
    if (lower.length <= 15) score += 1;

    //Negative signals (influencer account)
    if (lower.includes("atlanta")) score -= 3;
    if (lower.includes("atl")) score -= 2;
    if (lower.includes("city")) score -= 2;
    if (lower.includes("resy")) score -= 2;
    if (lower.includes("blog")) score -= 4;
    if (lower.includes("guide")) score -= 4;
    if (lower.includes("media")) score -= 4;
    if (lower.includes("things")) score -= 3;
    if (lower.includes("bucket")) score -= 3;
    if (lower.includes("loves")) score -= 3;

    //Highest-scoring mention selected as place name
    if (score > bestScore) {
      bestScore = score;
      bestMention = name;
    }
  });

  if (bestMention) return cleanName(bestMention);
  return "Unknown Place";
}

function cleanName(text) {
  if (!text) return "N/A";

  return String(text)
    .toLowerCase()
    .replace(/^atl/, "")
    .replace(/^eat/, "")
    .replace(/^the/, "")
    .replace(/atlanta$/, "")
    .replace(/atl$/, "")
    .replace(/official$/, "")
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/-/g, " ")
    .replace(/local/g, " local")
    .replace(/westend/g, "west end")
    .replace(/eastatlanta/g, "east atlanta")
    .replace(/midtown/g, "midtown")
    .replace(/downtown/g, "downtown")
    .replace(/buckhead/g, "buckhead")
    .replace(/decatur/g, "decatur")
    .replace(/coffeehouse/g, "coffee house")
    .replace(/coffeeshop/g, "coffee shop")
    .replace(/coffeeshops/g, "coffee shops")
    .replace(/sandwichbar/g, "sandwich bar")
    .replace(/companybar/g, "company bar")
    .replace(/winebar/g, "wine bar")
    .replace(/juicebar/g, "juice bar")
    .replace(/barand/g, "bar and ")
    .replace(/andgrille/g, " and grille")
    .replace(/restaurant/g, " restaurant")
    .replace(/kitchen/g, " kitchen")
    .replace(/garden/g, " garden")
    .replace(/pizza/g, " pizza")
    .replace(/pizzeria/g, " pizzeria")
    .replace(/cafe/g, " cafe")
    .replace(/coffee/g, " coffee")
    .replace(/bar/g, " bar")
    .replace(/grill/g, " grill")
    .replace(/grille/g, " grille")
    .replace(/cantina/g, " cantina")
    .replace(/house/g, " house")
    .replace(/shop/g, " shop")
    .replace(/park/g, " park")
    .replace(/room/g, " room")
    .replace(/club/g, " club")
    .replace(/market/g, " market")
    .replace(/tacos/g, " tacos")
    .replace(/burger/g, " burger")
    .replace(/depot/g, " depot")
    .replace(/([a-z])([0-9])/g, "$1 $2")
    .replace(/([0-9])([a-z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b[a-z]/g, (char) => char.toUpperCase());
}

/* STATS PANEL */
function createStatsPanel(places) {
  const categories = {};

  places.forEach((p) => {
    const cat = (p.category || "misc").toLowerCase();
    categories[cat] = (categories[cat] || 0) + 1;
  });

  const panel = document.createElement("div");
  panel.className = "stats-panel";

  panel.innerHTML = `
    <div class="stat">
      <h4>Total Posts</h4>
      <p class="value">${places.length}</p>
    </div>

    <div class="categories">
      <h4>By Category</h4>
      ${Object.entries(categories)
        .map(
          ([cat, count]) => `
          <div class="category-stat">
            <span>${cleanName(cat)}</span>
            <span class="count">${count}</span>
          </div>
        `,
        )
        .join("")}
    </div>
  `;
  return panel;
}
