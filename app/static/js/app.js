/* MediQueue front-end interactions (vanilla JS) */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  ready(function () {
    /* Navbar shadow on scroll */
    const nav = document.getElementById("siteNav");
    if (nav) {
      const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 12);
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }

    /* Toasts */
    document.querySelectorAll(".toast-item").forEach(function (el) {
      if (window.bootstrap && bootstrap.Toast) {
        new bootstrap.Toast(el, { autohide: true, delay: 5200 }).show();
      }
    });

    /* Sidebar (tablet / mobile) */
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("menuToggle");
    const backdrop = document.getElementById("sidebarBackdrop");
    function closeSidebar() {
      if (!sidebar) return;
      sidebar.classList.remove("open");
      if (backdrop) backdrop.classList.remove("show");
      if (toggle) toggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }
    if (toggle && sidebar) {
      toggle.addEventListener("click", function () {
        const open = !sidebar.classList.contains("open");
        sidebar.classList.toggle("open", open);
        if (backdrop) backdrop.classList.toggle("show", open);
        toggle.setAttribute("aria-expanded", String(open));
        document.body.style.overflow = open ? "hidden" : "";
      });
    }
    if (backdrop) backdrop.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });

    /* Password visibility */
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const input = document.getElementById(btn.getAttribute("data-toggle-password"));
        if (!input) return;
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.innerHTML = show ? '<i class="fa-regular fa-eye-slash"></i>' : '<i class="fa-regular fa-eye"></i>';
        btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
      });
    });

    /* Copy booking id */
    document.querySelectorAll("[data-copy]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const text = btn.getAttribute("data-copy");
        const done = () => {
          const original = btn.innerHTML;
          btn.innerHTML = '<i class="fa-solid fa-check"></i>';
          setTimeout(() => (btn.innerHTML = original), 1600);
        };
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(done).catch(done);
        else done();
      });
    });

    /* Loading state on submit buttons */
    document.querySelectorAll("form[data-loading]").forEach(function (form) {
      form.addEventListener("submit", function () {
        const btn = form.querySelector("button[type=submit]");
        if (btn) {
          btn.classList.add("is-loading");
          setTimeout(() => btn.classList.remove("is-loading"), 8000);
        }
      });
    });

    /* Tooltips */
    if (window.bootstrap) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
      });
    }

    initBooking();
    initCountdowns();
  });

  /* ------------------------------------------------------------------ */
  /* Booking page: slot selection, live refresh, summary                  */
  /* ------------------------------------------------------------------ */
  function initBooking() {
    const form = document.getElementById("bookingForm");
    const grid = document.getElementById("slotGrid");
    if (!form || !grid) return;

    const hidden = document.getElementById("slotId");
    const selectedLabel = document.getElementById("selectedTime");
    const selectedSlotText = document.getElementById("selectedSlotText");
    const submitBtn = document.getElementById("confirmBooking");
    const emptyNote = document.getElementById("slotEmpty");
    const doctorId = grid.getAttribute("data-doctor-id");
    const date = grid.getAttribute("data-date");
    let selectedId = hidden ? hidden.value : "";

    function refreshSummary() {
      const btn = grid.querySelector(".slot-btn.selected");
      const label = btn ? btn.getAttribute("data-label") : "";
      if (selectedLabel) selectedLabel.textContent = label || "—";
      if (selectedSlotText) selectedSlotText.textContent = label || "Not selected";
      if (submitBtn) submitBtn.disabled = !btn;
      if (!btn && hidden) hidden.value = "";
      if (emptyNote) emptyNote.style.display = grid.querySelector(".slot-btn:not(:disabled)") ? "none" : "block";
    }

    grid.querySelectorAll(".slot-btn[data-slot-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.disabled) return;
        grid.querySelectorAll(".slot-btn.selected").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        selectedId = btn.getAttribute("data-slot-id");
        if (hidden) hidden.value = selectedId;
        refreshSummary();
      });
    });
    refreshSummary();

    if (!doctorId || !date) return;

    function poll() {
      fetch("/api/doctors/" + doctorId + "/slots?date=" + encodeURIComponent(date), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      })
        .then((r) => (r.ok ? r.json() : null))
        .then(function (data) {
          if (!data || !data.slots) return;
          let conflict = false;
          data.slots.forEach(function (slot) {
            const btn = grid.querySelector('.slot-btn[data-slot-id="' + slot.id + '"]');
            if (!btn) return;
            const isSelected = btn.classList.contains("selected");
            btn.disabled = !slot.available;
            btn.classList.toggle("booked", !slot.available);
            btn.classList.toggle("blocked", slot.status === "BLOCKED");
            const icon = btn.querySelector(".slot-lock");
            if (icon) icon.style.visibility = slot.available ? "hidden" : "visible";
            if (isSelected && !slot.available) {
              btn.classList.remove("selected");
              conflict = true;
            }
          });
          if (conflict) {
            selectedId = "";
            if (hidden) hidden.value = "";
            refreshSummary();
            showNote("That slot was just booked by another patient. Please choose another available time.");
          }
          refreshSummary();
        })
        .catch(function () { /* offline / transient - keep UI usable */ });
    }

    function showNote(message) {
      if (!emptyNote) return;
      emptyNote.textContent = message;
      emptyNote.style.display = "block";
      emptyNote.className = "alert alert-warning mt-3 mb-0";
    }

    setInterval(poll, 30000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) poll();
    });
  }

  /* ------------------------------------------------------------------ */
  /* Countdown on patient dashboard                                        */
  /* ------------------------------------------------------------------ */
  function initCountdowns() {
    const nodes = document.querySelectorAll("[data-countdown]");
    if (!nodes.length) return;

    function tick() {
      nodes.forEach(function (node) {
        const target = new Date(node.getAttribute("data-countdown")).getTime();
        const diff = target - Date.now();
        const out = node.querySelector(".countdown") || node;
        if (isNaN(target)) return;
        if (diff <= 0) {
          out.innerHTML = '<div><strong>Now</strong><span>time</span></div>';
          return;
        }
        const days = Math.floor(diff / 86400000);
        const hours = Math.floor((diff % 86400000) / 3600000);
        const mins = Math.floor((diff % 3600000) / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        out.innerHTML =
          "<div><strong>" + days + "</strong><span>days</span></div>" +
          "<div><strong>" + hours + "</strong><span>hrs</span></div>" +
          "<div><strong>" + mins + "</strong><span>min</span></div>" +
          "<div><strong>" + secs + "</strong><span>sec</span></div>";
      });
    }
    tick();
    setInterval(tick, 1000);
  }
})();
