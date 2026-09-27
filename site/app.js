/* cloudflip: map, 7-day strip, headline, best bets (nearest first among equals), search and a detail view for each Munro.
   Data comes from data/scores.js (window.CLOUDFLIP), written by scripts/site_export_function.py. */
(function () {
  'use strict';

  var DATA = window.CLOUDFLIP;
  var WORDS = ['Unlikely', 'Possible', 'Likely'];
  var MARKS = ['&#10007;', '~', '&#10003;'];
  var CHECKS = [['icon-lid', 'Warm lid'], ['icon-cloud', 'Cloud below'], ['icon-summit', 'Clear summit'], ['icon-wind', 'Still air']];
  var STYLE = { //marker look per status: bigger and brighter for better mornings
    2: { radius: 9, fillColor: '#f2a900', color: '#ffffff', weight: 2, fillOpacity: 1 },
    1: { radius: 7, fillColor: '#f7c59f', color: '#e07b00', weight: 2, fillOpacity: 1 },
    0: { radius: 5, fillColor: '#9aa5b3', color: '#ffffff', weight: 1, fillOpacity: 0.9 }
  };

  var $ = function (id) { return document.getElementById(id); };
  var munros = {};
  DATA.munros.forEach(function (m) { munros[m.id] = m; });

  var state = { day: 0, selected: null, mode: 'best', query: '', here: null };

  /* ---------- formatting ---------- */
  function ukTime(utc) {
    var d = new Date(/Z$/.test(utc) ? utc : utc + 'Z');
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London' });
  }
  function dayLabel(date, opts) {
    return new Date(date + 'T12:00:00Z').toLocaleDateString('en-GB', Object.assign({ timeZone: 'Europe/London' }, opts));
  }
  function longDay(date) { return dayLabel(date, { weekday: 'short', day: 'numeric', month: 'short' }); }
  function esc(text) { return String(text).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function passes(s) { return s.g.filter(function (g) { return g === 2; }).length; }
  function rank(s) { return s.r * 100 + passes(s) * 10 + s.g.reduce(function (a, b) { return a + b; }, 0); }
  function dot(r) { return '<i class="dot dot-' + r + '"></i>'; }
  function pips(s) {
    return '<span class="pips">' + s.g.map(function (g) { return '<i class="g' + g + '"></i>'; }).join('') + '</span>';
  }

  /* ---------- the words ---------- */
  function mainProblem(s) {
    if (s.g[0] === 0) return s.lapse === null ? 'no warm lid the forecast can see' : 'no warm lid';
    if (s.g[1] === 0) return 'too dry below the summit';
    if (s.g[2] === 0) return 'summit likely in cloud';
    if (s.g[3] === 0) return 'too windy (' + s.wb + ' km/h)';
    return 'some checks only borderline';
  }

  function checkValues(s) {
    var lid;
    if (s.lapse === null) lid = 'not enough forecast levels below the top to tell';
    else if (s.lapse > 0) lid = 'warmer layer at ~' + s.top + ' m';
    else if (s.g[0] === 1) lid = 'weak, air barely cools with height';
    else lid = 'none, air cools with height';
    var cloud = s.rhb === null ? 'nothing to check' : 'damp air (' + s.rhb + '% humidity)';
    var summit = (s.g[2] === 2 ? 'dry' : s.g[2] === 1 ? 'hazy' : 'in cloud') + ' (' + s.rhs + '% humidity)';
    var wind = s.wb + ' km/h below the top';
    return [lid, cloud, summit, wind];
  }

  function verdict(s) {
    if (s.r === 2) return 'Good chance of standing above a sea of cloud.';
    if (s.r === 1) return 'Some chance of a cloud sea below the summit, worth keeping an eye on.';
    var good = [];
    if (s.g[0] === 2) good.push('a warm lid sits at ~' + s.top + ' m');
    if (s.g[1] === 2) good.push('the glens are damp');
    if (s.g[2] === 2) good.push('the summit should be clear');
    var bad;
    if (s.lapse === null) bad = 'the forecast can’t show a warm lid this far below the summit';
    else if (s.g[0] === 0) bad = 'there is no warm lid to trap cloud in the glens';
    else if (s.g[1] === 0) bad = 'the air below the summit is too dry for a cloud sea';
    else if (s.g[2] === 0) bad = 'the summit is likely to be in the cloud, not above it';
    else bad = s.wb + ' km/h winds would probably break the cloud up';
    if (!good.length) return bad.charAt(0).toUpperCase() + bad.slice(1) + '.';
    var text = good.length > 1 ? good.slice(0, -1).join(', ') + ' and ' + good[good.length - 1] : good[0];
    return text.charAt(0).toUpperCase() + text.slice(1) + ', but ' + bad + '.';
  }

  /* ---------- the hill picture ---------- */
  function hillPicture(m, s) {
    var ground = m.ground, summit = m.h, topY = 34, baseY = 128;
    function yOf(h) {
      var f = (h - ground) / Math.max(summit - ground, 1);
      return baseY - Math.min(Math.max(f, 0), 1) * (baseY - topY);
    }
    var halo = ' stroke="#eaf2fa" stroke-width="3" paint-order="stroke"';
    var p = ['<rect width="280" height="140" rx="10" fill="#eaf2fa"/>'];
    if (s.g[2] === 2) p.push('<circle cx="236" cy="26" r="11" fill="#f2a900"/>');
    p.push('<path d="M20 ' + baseY + ' L78 86 L100 98 L140 ' + topY + ' L186 92 L206 84 L262 ' + baseY + ' Z" fill="#7b8f79"/>');
    p.push('<path d="M126 ' + (topY + 16) + ' L140 ' + topY + ' L154 ' + (topY + 16) + ' Z" fill="#a9b8a7"/>');
    if (s.g[1] > 0) { //cloud sea up to the lid if there is one below the summit, otherwise about halfway
      var lidBelow = s.top !== null && s.top < summit;
      var seaY = lidBelow ? yOf(s.top) : (baseY + topY) / 2 + 12;
      var waves = '';
      for (var i = 0; i < 7; i++) waves += ' q 10 -7 20 0 q 10 7 20 0';
      p.push('<path d="M0 ' + seaY.toFixed(0) + waves + ' V140 H0 Z" fill="#ffffff" opacity="' + (s.g[1] === 2 ? 0.95 : 0.55) + '"/>');
    }
    if (s.g[0] > 0 && s.top !== null) {
      var lidY = (yOf(s.top) - 4).toFixed(0);
      p.push('<line x1="8" x2="272" y1="' + lidY + '" y2="' + lidY + '" stroke="#e07b00" stroke-width="2" stroke-dasharray="6 4" opacity="' + (s.g[0] === 2 ? 1 : 0.5) + '"/>');
      p.push('<text x="10" y="' + (lidY - 4) + '" font-size="10" fill="#b35f00"' + halo + '>warm lid ~' + s.top + ' m</text>');
    }
    if (s.g[2] === 0) p.push('<path d="M112 ' + (topY + 8) + ' a9 9 0 0 1 12 -9 a12 12 0 0 1 22 -2 a9 9 0 0 1 16 11 z" fill="#c9d3dc"/>');
    var streaks = s.g[3] === 2 ? 0 : s.g[3] === 1 ? 1 : 3;
    for (var j = 0; j < streaks; j++) {
      p.push('<path d="M' + (196 + (j % 2) * 14) + ' ' + (100 + j * 9) + ' h26 l-5 -3 m5 3 l-5 3" fill="none" stroke="#3d4b58" stroke-width="1.6" stroke-linecap="round"/>');
    }
    if (streaks) p.push('<text x="194" y="94" font-size="10" fill="#3d4b58"' + halo + '>' + s.wb + ' km/h</text>');
    p.push('<text x="140" y="' + (topY - 6) + '" font-size="10" text-anchor="middle" fill="#1f2a3a">' + summit + ' m</text>');
    return '<svg class="hill-picture" viewBox="0 0 280 140" role="img" aria-label="Side view of the hill showing the forecast">' + p.join('') + '</svg>';
  }

  /* ---------- map ---------- */
  var map = L.map('map', { zoomControl: true }).setView([57.0, -4.6], 7);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16,
    attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, OpenStreetMap contributors, and the GIS User Community'
  }).addTo(map);

  var markers = {};
  DATA.munros.forEach(function (m) {
    var marker = L.circleMarker([m.lat, m.lon], STYLE[0]).addTo(map);
    marker.on('click', function () { select(m.id, false); });
    markers[m.id] = marker;
  });
  var ring = L.circleMarker([0, 0], { radius: 15, color: '#1f2a3a', weight: 2.5, fill: false, interactive: false });

  function drawMarkers() {
    var scores = DATA.days[state.day].scores;
    var order = [0, 1, 2];
    order.forEach(function (r) { //draw better mornings last, so they sit on top
      DATA.munros.forEach(function (m) {
        var s = scores[m.id];
        if (!s || s.r !== r) return;
        markers[m.id].setStyle(STYLE[r]).setRadius(STYLE[r].radius);
        markers[m.id].unbindTooltip().bindTooltip(esc(m.name) + ' &middot; ' + WORDS[r], { direction: 'top', offset: [0, -6] });
        markers[m.id].bringToFront();
      });
    });
    if (state.selected !== null) {
      ring.setLatLng(markers[state.selected].getLatLng()).addTo(map).bringToFront();
    } else {
      ring.remove();
    }
  }

  /* ---------- panel ---------- */
  function drawDays() {
    $('days').innerHTML = DATA.days.map(function (d, i) {
      var list = Object.keys(d.scores).map(function (k) { return d.scores[k]; });
      var best = Math.max.apply(null, list.map(passes));
      var bestStatus = Math.max.apply(null, list.map(function (s) { return s.r; }));
      var likely = list.filter(function (s) { return s.r === 2; }).length;
      var possible = list.filter(function (s) { return s.r === 1; }).length;
      var title = longDay(d.date) + ': ' + likely + ' likely, ' + possible + ' possible, best Munro passes ' + best + ' of 4 checks';
      return '<button class="day" type="button" data-day="' + i + '" aria-pressed="' + (i === state.day) + '" title="' + title + '">' +
        '<span class="day-name">' + dayLabel(d.date, { weekday: 'short' }) + '</span>' +
        '<span class="day-num">' + dayLabel(d.date, { day: 'numeric' }) + '</span>' +
        '<span class="day-bar"><i class="best-' + bestStatus + '" style="width:' + (best / 4 * 100) + '%"></i></span></button>';
    }).join('');
  }

  function tieBreak(a, b) { //equally good munros: nearest first once we know where you are, otherwise alphabetical
    if (state.here) return distanceKm(state.here, a) - distanceKm(state.here, b);
    return a.name.localeCompare(b.name);
  }

  function ranked() {
    var scores = DATA.days[state.day].scores;
    return DATA.munros.filter(function (m) { return scores[m.id]; })
      .sort(function (a, b) { return rank(scores[b.id]) - rank(scores[a.id]) || tieBreak(a, b); });
  }

  function away(m) { return state.here ? ' (' + Math.round(distanceKm(state.here, m)) + ' km away)' : ''; }

  function drawHeadline() {
    var day = DATA.days[state.day];
    var list = ranked();
    var scores = day.scores;
    var likely = list.filter(function (m) { return scores[m.id].r === 2; });
    var possible = list.filter(function (m) { return scores[m.id].r === 1; });
    var best = list[0], s = scores[best.id];
    var ties = list.filter(function (m) { return rank(scores[m.id]) === rank(s); }).length - 1;
    var bestName = '<b>' + esc(best.name) + '</b>' + away(best) +
      (ties ? ' and ' + ties + ' other' + (ties > 1 ? 's' : '') + ' just as good' : '');
    var kicker = 'Sunrise, ' + longDay(day.date) + (day.sunrise ? ' &middot; about ' + ukTime(day.sunrise) : '');
    var title, text;
    if (likely.length) {
      title = likely.length + ' Munro' + (likely.length > 1 ? 's look' : ' looks') + ' likely for a cloud sea';
      text = 'Best bet: ' + bestName + ', around ' + ukTime(s.t) + '.' +
        (possible.length ? ' ' + possible.length + ' more possible.' : '');
    } else if (possible.length) {
      title = 'A chance of a cloud sea on ' + possible.length + ' Munro' + (possible.length > 1 ? 's' : '');
      text = 'Best bet: ' + bestName + ', around ' + ukTime(s.t) + ', with all four checks at least borderline.';
    } else {
      title = 'No cloud inversions expected';
      text = 'Closest call: ' + bestName + ', at ' + ukTime(s.t) + '. ' + passes(s) + ' of 4 checks ' + (passes(s) === 1 ? 'passes' : 'pass') + ', but ' + mainProblem(s) + '.';
    }
    $('headline').innerHTML = '<p class="kicker">' + kicker + '</p><h2>' + title + '</h2><p>' + text + '</p>';
  }

  function distanceKm(a, b) {
    var R = 6371, rad = Math.PI / 180;
    var dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function drawList() {
    var scores = DATA.days[state.day].scores;
    var items, title;
    if (state.mode === 'search') {
      var q = state.query.toLowerCase();
      items = DATA.munros.filter(function (m) { return m.name.toLowerCase().indexOf(q) !== -1; })
        .sort(function (a, b) { return a.name.localeCompare(b.name); }).slice(0, 30);
      title = 'Matching Munros';
    } else {
      items = ranked().slice(0, 10);
      title = 'Best bets' + (state.here ? ' near you' : '') + ', ' + longDay(DATA.days[state.day].date);
    }
    $('list-title').textContent = title;
    if (!items.length) {
      $('bets').innerHTML = '<li class="empty">No Munro matches that name.</li>';
      return;
    }
    $('bets').innerHTML = items.map(function (m) {
      var s = scores[m.id];
      var sub = m.h + ' m &middot; ' + (state.here ? Math.round(distanceKm(state.here, m)) + ' km &middot; ' : '') + 'best ' + ukTime(s.t);
      return '<li><button class="bet" type="button" data-id="' + m.id + '">' + dot(s.r) +
        '<span><span class="bet-name">' + esc(m.name) + '</span><br><span class="bet-sub">' + sub + '</span></span>' +
        '<span class="bet-score">' + pips(s) + '<br>' + passes(s) + '/4 checks</span></button></li>';
    }).join('');
  }

  function drawDetail() {
    var m = munros[state.selected];
    var day = DATA.days[state.day];
    var s = day.scores[m.id];
    var values = checkValues(s);
    var checks = CHECKS.map(function (c, i) {
      return '<li><svg aria-hidden="true"><use href="#' + c[0] + '"/></svg><div><b>' + c[1] +
        '<span class="mark mark-' + s.g[i] + '">' + MARKS[s.g[i]] + '</span></b><span>' + values[i] + '</span></div></li>';
    }).join('');
    var week = DATA.days.map(function (d, i) {
      var ws = d.scores[m.id];
      return '<button type="button" data-day="' + i + '" aria-pressed="' + (i === state.day) + '" title="' + longDay(d.date) + ': ' + WORDS[ws.r] + ', ' + passes(ws) + ' of 4 checks">' +
        dayLabel(d.date, { weekday: 'short' }) + dot(ws.r) + '</button>';
    }).join('');
    var links = [];
    if (m.link) links.push('<a href="' + esc(m.link) + '" target="_blank" rel="noopener">Routes and walk logs (Hill Bagging)</a>');
    links.push('<a href="https://www.mwis.org.uk/forecasts/scottish" target="_blank" rel="noopener">MWIS mountain forecast</a>');
    $('detail-view').innerHTML = '<div class="detail">' +
      '<button class="back" type="button" id="back">&larr; All Munros</button>' +
      '<h2>' + esc(m.name) + '</h2>' +
      '<p class="meta">' + m.h + ' m &middot; best around ' + ukTime(s.t) + ', ' + longDay(day.date) + '</p>' +
      '<span class="pill">' + dot(s.r) + WORDS[s.r] + ' &middot; ' + passes(s) + ' of 4 checks</span>' +
      '<div style="margin-top:10px">' + hillPicture(m, s) + '</div>' +
      '<p class="verdict">' + verdict(s) + '</p>' +
      '<ul class="checks">' + checks + '</ul>' +
      '<p class="extra">Wind on the summit itself ' + s.ws + ' km/h &middot; pressure ' + s.p + ' hPa</p>' +
      '<h3 class="section-title" style="margin-top:16px">This week at ' + esc(m.name) + '</h3>' +
      '<div class="week" id="week">' + week + '</div>' +
      '<div class="links">' + links.join('') + '</div></div>';
    $('back').addEventListener('click', function () { select(null); });
    $('week').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (b) setDay(+b.dataset.day);
    });
  }

  function render() {
    drawDays();
    drawHeadline();
    drawMarkers();
    var showDetail = state.selected !== null;
    $('list-view').hidden = showDetail;
    $('detail-view').hidden = !showDetail;
    if (showDetail) drawDetail(); else drawList();
    var hash = '#day=' + DATA.days[state.day].date + (showDetail ? '&munro=' + state.selected : '');
    if (location.hash !== hash) history.replaceState(null, '', hash);
  }

  /* ---------- actions ---------- */
  function setDay(i) { state.day = i; render(); }

  function select(id, pan) {
    state.selected = id;
    render();
    if (id !== null) {
      if (pan !== false) map.panTo(markers[id].getLatLng());
      if (window.matchMedia('(max-width: 800px)').matches) $('detail-view').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  $('days').addEventListener('click', function (e) {
    var b = e.target.closest('.day');
    if (b) setDay(+b.dataset.day);
  });
  $('bets').addEventListener('click', function (e) {
    var b = e.target.closest('.bet');
    if (b) select(+b.dataset.id);
  });
  $('search').addEventListener('input', function (e) {
    state.query = e.target.value.trim();
    state.mode = state.query ? 'search' : 'best';
    state.selected = null;
    render();
  });
  /* location: only used to break ties and show distances. Asked for when "Near me" is pressed,
     or used straight away if the browser already allows it, so the page never opens with a pop-up. */
  var youMarker = L.circleMarker([0, 0], { radius: 6, color: '#ffffff', weight: 2, fillColor: '#2f6fd6', fillOpacity: 1, interactive: false });

  function locate(quiet) {
    var button = $('near-me');
    if (!navigator.geolocation) { if (!quiet) button.textContent = 'Not available'; return; }
    if (!quiet) button.textContent = 'Finding you\u2026';
    navigator.geolocation.getCurrentPosition(function (pos) {
      state.here = { lat: pos.coords.latitude, lon: pos.coords.longitude };
      youMarker.setLatLng([state.here.lat, state.here.lon]).addTo(map);
      button.textContent = 'Using your location';
      button.setAttribute('aria-pressed', 'true');
      if (!quiet) {
        state.mode = 'best'; state.selected = null; state.query = ''; $('search').value = '';
        map.setView([state.here.lat, state.here.lon], 8);
      }
      render();
    }, function () {
      if (quiet) return;
      button.textContent = 'Location blocked';
      setTimeout(function () { button.textContent = 'Near me'; }, 2500);
    }, { maximumAge: 600000, timeout: 15000 });
  }

  $('near-me').addEventListener('click', function () { locate(false); });
  if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'geolocation' }).then(function (p) {
      if (p.state === 'granted') locate(true);
    }).catch(function () {});
  }
  $('how').addEventListener('click', function () { $('explainer').hidden = false; $('explainer-close').focus(); });
  $('explainer-close').addEventListener('click', function () { $('explainer').hidden = true; });
  $('explainer').addEventListener('click', function (e) { if (e.target === this) this.hidden = true; });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (!$('explainer').hidden) $('explainer').hidden = true;
    else if (state.selected !== null) select(null);
  });

  /* ---------- start: today's morning (or a shared link's day and Munro) ---------- */
  var today = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/London' }); //YYYY-MM-DD
  var start = DATA.days.findIndex(function (d) { return d.date >= today; });
  state.day = start === -1 ? 0 : start;
  var params = new URLSearchParams(location.hash.slice(1));
  var hashDay = DATA.days.findIndex(function (d) { return d.date === params.get('day'); });
  if (hashDay !== -1) state.day = hashDay;
  if (munros[params.get('munro')]) state.selected = +params.get('munro');

  $('fetched').textContent = 'Forecast fetched ' + new Date(DATA.meta.run_time).toLocaleString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/London'
  }) + ' (Met Office UK model).';
  render();
})();
