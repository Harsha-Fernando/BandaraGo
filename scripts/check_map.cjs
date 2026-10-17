// Map behavior checks without a browser. Actual rendering/performance needs browser QA.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const code = fs.readFileSync('static/js/map.js', 'utf8');
function run(data, withLeaflet = true) {
  const container = {dataset: {}};
  const status = {};
  const events = {};
  const markers = [];
  let tileOptions;
  const map = {setView(point, zoom) {this.view = [point, zoom];}, fitBounds(points) {this.bounds = points;}};
  const tiles = {on(name, callback) {events[name] = callback; return this;}, addTo() {}};
  const L = {map: () => map, tileLayer: (url, options) => { tileOptions = options; return tiles; }, marker(point, options) {
    const marker = {point, options, addTo() {return this;}, bindPopup(label) {this.label = label; return this;}};
    markers.push(marker); return marker;
  }};
  const document = {getElementById(id) {return {map: container, 'map-status': status, 'map-data': {textContent: data}}[id];}, createElement() {return {};}};
  vm.runInNewContext(code, {document, window: {L: withLeaflet ? L : undefined}, L, performance: {now: () => 123}});
  return {container, status, markers, map, events, tileOptions};
}
const point = {name: '<img src=x onerror=alert(1)>', latitude: 6.6, longitude: 79.9};
let result = run(JSON.stringify([point]));
assert.equal(result.markers.length, 1);
assert.equal(result.markers[0].label.textContent, point.name);
assert.equal(result.container.dataset.markersReady, 'true');
assert.equal(result.map.view[1], 15);
assert.equal(result.tileOptions.referrerPolicy, 'strict-origin-when-cross-origin');
result.events.tileerror(); assert.match(result.status.textContent, /could not load/);
result.events.load(); assert.match(result.status.textContent, /could not load/);
result = run(JSON.stringify([point, {...point, latitude: 6.7}]));
assert.equal(result.map.bounds.length, 2);
assert.match(run('invalid').status.textContent, /unavailable/);
assert.match(run('[]').status.textContent, /unavailable/);
assert.match(run(JSON.stringify([point]), false).status.textContent, /unavailable/);
console.log('Map behavior checks passed: marker coordinates, safe labels, framing, tile errors, malformed/empty data, and missing Leaflet. Actual browser rendering is checked separately.');
