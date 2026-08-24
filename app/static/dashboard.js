// The dashboard loads its data AFTER the page renders, behind a deliberate
// server-side delay. That is the whole point: content appears asynchronously,
// so a test that does not wait properly will race it. This is the page the
// explicit-wait work is built around.
(function () {
  "use strict";

  function el(sel) {
    return document.querySelector('[data-testid="' + sel + '"]');
  }

  function renderGames(games) {
    var list = el("games-list");
    list.innerHTML = "";
    games.forEach(function (g) {
      var li = document.createElement("li");
      li.setAttribute("data-testid", "game-row");
      li.setAttribute("data-id", g.id);
      li.textContent = g.visitor + " @ " + g.home + " — " + g.status;
      list.appendChild(li);
    });
    el("no-games").hidden = games.length > 0;
  }

  function renderInjuries(injuries) {
    var list = el("injury-list");
    list.innerHTML = "";
    injuries.forEach(function (p) {
      var li = document.createElement("li");
      li.setAttribute("data-testid", "injury-row");
      li.setAttribute("data-id", p.id);
      li.setAttribute("data-status", p.injury_status);
      li.textContent = p.first_name + " " + p.last_name + " (" + p.team + ") — " +
        p.injury_status + ": " + (p.injury_note || "");
      list.appendChild(li);
    });
    el("no-injuries").hidden = injuries.length > 0;
  }

  function render(data) {
    el("dashboard-date").textContent = data.date;
    el("dashboard-roster-count").textContent = data.roster_count;
    renderGames(data.games);
    renderInjuries(data.injuries);
    // Order matters: reveal content, then remove the spinner, so there is
    // never a frame with neither on screen.
    el("dashboard-content").hidden = false;
    var loading = el("dashboard-loading");
    loading.parentNode.removeChild(loading);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = document.getElementById("dashboard");
    var url = "/api/dashboard";
    if (root.dataset.date) {
      url += "?date=" + encodeURIComponent(root.dataset.date);
    }
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      })
      .then(render)
      .catch(function () {
        var loading = el("dashboard-loading");
        if (loading) { loading.parentNode.removeChild(loading); }
        el("dashboard-error").hidden = false;
      });
  });
})();
