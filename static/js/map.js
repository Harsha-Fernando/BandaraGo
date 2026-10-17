(() => {
  const container = document.getElementById('map');
  const status = document.getElementById('map-status');
  if (!container || !status) return;
  try {
    const places = JSON.parse(document.getElementById('map-data').textContent);
    if (!window.L || !places.length) throw new Error('Map unavailable');
    const map = L.map(container, {scrollWheelZoom: false});
    const bounds = [];
    places.forEach((place) => {
      const label = document.createElement('span');
      label.textContent = place.name;
      const point = [place.latitude, place.longitude];
      L.marker(point, {title: place.name}).addTo(map).bindPopup(label);
      bounds.push(point);
    });
    if (bounds.length === 1) map.setView(bounds[0], 15);
    else map.fitBounds(bounds, {padding: [35, 35], maxZoom: 15});
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    let failed = false;
    tiles.on('tileerror', () => {
      failed = true;
      status.textContent = 'Map tiles could not load. Coordinates and an OpenStreetMap link are available below.';
    });
    tiles.on('load', () => {
      if (!failed) status.textContent = 'Use the + and − buttons to zoom, or drag to pan.';
    });
    tiles.addTo(map);
    status.textContent = 'Location marker ready. Loading map tiles…';
    container.dataset.markersReady = 'true';
    container.dataset.markersReadyMs = Math.round(performance.now());
  } catch (error) {
    status.textContent = 'The interactive map is unavailable. Use the coordinates or OpenStreetMap links below.';
  }
})();
