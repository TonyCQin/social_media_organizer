# Places To Go Dashboard

A lightweight frontend dashboard for exploring restaurant and venue recommendations extracted from short-form social media videos.

This interface displays processed location data from `final_post_classifications.csv` and allows users to search, filter, and save places they want to visit.

---

## Features

### Search
Search places by detected venue name or cuisine.

### Category Filters
Browse recommendations by category:

- Dinner
- Drinks
- Brunch
- Dessert
- Event

### Saved Places
Users can favorite places and quickly view saved recommendations later.

Favorites are stored in browser `localStorage`, so they persist after refresh.

### Duplicate Removal
Multiple social media posts may mention the same venue.  
The dashboard removes duplicate cards so each place appears once.

### Place Name Detection
When source data contains generic or noisy location labels, the app uses caption mentions (`@handles`) and a weighted scoring system to infer the most likely business name.

### Stats Panel
Displays:

- Total posts analyzed
- Counts by category

---

## Tech Stack

- HTML
- CSS
- Vanilla JavaScript
- Papa Parse (CSV parsing)

---

## Project Structure

```text
frontend/
├── index.html
├── index.js
├── styles/
│   ├── global.css
│   └── components.css
└── data/
    └── final_post_classifications.csv