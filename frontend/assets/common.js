/* ============================================================
   RetailPool AI — shared i18n + common behaviors + auth
   ============================================================ */

/* ── API Base URL ──────────────────────────────────────────── */
const RP_API_BASE = window.location.origin;

/* ── Global Fetch Interceptor ──────────────────────────────── */
const rpOriginalFetch = window.fetch;
window.fetch = async function(...args) {
  const response = await rpOriginalFetch(...args);
  if (response.status === 401) {
    try {
      const clone = response.clone();
      const err = await clone.json();
      if (err && err.detail && typeof err.detail === 'string' && (err.detail.includes('Signature has expired') || err.detail.includes('expired'))) {
        alert('Ваша сессия устарела. Пожалуйста, войдите снова.');
        rpLogout();
        // Return a never-resolving promise so local catch blocks don't fire generic alerts
        return new Promise(() => {});
      }
    } catch(e) {}
  }
  return response;
};

/* ── Auth Utilities ────────────────────────────────────────── */
function rpGetToken() {
  return localStorage.getItem('rp_token');
}
function rpGetUser() {
  try { return JSON.parse(localStorage.getItem('rp_user')); } catch { return null; }
}
function rpSetAuth(token, user) {
  localStorage.setItem('rp_token', token);
  localStorage.setItem('rp_user', JSON.stringify(user));
}
function rpLogout() {
  localStorage.removeItem('rp_token');
  localStorage.removeItem('rp_user');
  window.location.href = '/auth.html?view=login';
}
function rpAuthHeaders() {
  const token = rpGetToken();
  return token ? { 'Authorization': 'Bearer ' + token } : {};
}

/* ── i18n ──────────────────────────────────────────────────── */
const RP_I18N = {
  ru: {
    nav_home: "Главная", nav_scanner: "Сканер", nav_pools: "Пулы", nav_pricing: "Тарифы", nav_cta: "Начать",
    nav_login: "Войти", nav_register: "Регистрация", nav_logout: "Выйти", nav_profile: "Профиль",
    footer_desc: "ИИ-радар по Kaspi.kz: находим ниши со слабой конкуренцией и собираем синдикаты совместных закупок для МСБ Казахстана.",
    footer_product: "Продукт", footer_company: "Компания", footer_legal: "Документы",
    footer_l_scanner: "Niche Scanner", footer_l_pools: "Co-Buying пулы", footer_l_pricing: "Тарифы", footer_l_demo: "Демо",
    footer_l_about: "О проекте", footer_l_contact: "Контакты", footer_l_telegram: "Telegram-бот",
    footer_l_privacy: "Политика конфиденциальности", footer_l_terms: "Условия использования", footer_l_offer: "Публичная оферта",
    footer_rights: "© 2025 RetailPool AI. Все права защищены.",
    footer_built: "Алматы · Казахстан",
  },
  en: {
    nav_home: "Home", nav_scanner: "Scanner", nav_pools: "Pools", nav_pricing: "Pricing", nav_cta: "Get started",
    nav_login: "Sign in", nav_register: "Sign up", nav_logout: "Sign out", nav_profile: "Profile",
    footer_desc: "An AI radar for Kaspi.kz: we find low-competition niches and form co-buying syndicates for Kazakhstani SMBs.",
    footer_product: "Product", footer_company: "Company", footer_legal: "Legal",
    footer_l_scanner: "Niche Scanner", footer_l_pools: "Co-Buying pools", footer_l_pricing: "Pricing", footer_l_demo: "Demo",
    footer_l_about: "About", footer_l_contact: "Contact", footer_l_telegram: "Telegram bot",
    footer_l_privacy: "Privacy policy", footer_l_terms: "Terms of service", footer_l_offer: "Public offer",
    footer_rights: "© 2025 RetailPool AI. All rights reserved.",
    footer_built: "Almaty · Kazakhstan",
  }
};

let RP_LANG = localStorage.getItem('rp_lang') || 'ru';

function rpApplyTranslations() {
  const t = RP_I18N[RP_LANG];
  document.querySelectorAll('[data-i]').forEach(el => {
    const key = el.getAttribute('data-i');
    if (t[key] !== undefined) el.innerHTML = t[key];
  });
  document.querySelectorAll('[data-i_ph]').forEach(el => {
    const key = el.getAttribute('data-i_ph');
    if (t[key] !== undefined) el.placeholder = t[key];
  });
  document.documentElement.lang = RP_LANG;
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.classList.toggle('active', b.getAttribute('data-lang') === RP_LANG);
  });
  // Update auth nav buttons
  rpUpdateAuthNav();
  if (typeof onLangChange === 'function') onLangChange();
}

function rpSetLang(l) {
  RP_LANG = l;
  localStorage.setItem('rp_lang', l);
  rpApplyTranslations();
}

/* ── Auth Nav ──────────────────────────────────────────────── */
function rpUpdateAuthNav() {
  const navRight = document.querySelector('.nav-right');
  if (!navRight) return;

  // Remove existing auth buttons
  navRight.querySelectorAll('.auth-nav-btn, .auth-user-badge').forEach(el => el.remove());

  const t = RP_I18N[RP_LANG];
  const user = rpGetUser();

  if (user && rpGetToken()) {
    // Logged in — show user badge + logout
    const badge = document.createElement('div');
    badge.className = 'auth-user-badge';
    badge.style.cssText = 'display:flex;align-items:center;gap:8px;font-size:13px;';

    const name = document.createElement('span');
    name.style.cssText = 'color:var(--text-2);font-size:12px;';
    name.textContent = user.full_name || user.email;

    const logoutBtn = document.createElement('button');
    logoutBtn.className = 'auth-nav-btn';
    logoutBtn.style.cssText = 'background:none;border:1px solid var(--border-2);color:var(--text-2);border-radius:var(--radius-sm);padding:7px 14px;font-size:12px;cursor:pointer;font-family:var(--font-display);font-weight:500;transition:all 0.15s;';
    logoutBtn.textContent = t.nav_logout;
    logoutBtn.onclick = rpLogout;

    badge.appendChild(name);
    badge.appendChild(logoutBtn);

    // Insert before burger button
    const burger = navRight.querySelector('.nav-burger');
    if (burger) {
      navRight.insertBefore(badge, burger);
    } else {
      navRight.appendChild(badge);
    }

    // Replace CTA button
    const cta = navRight.querySelector('.btn-nav-cta');
    if (cta) cta.style.display = 'none';
  } else {
    // Not logged in — show login link
    const cta = navRight.querySelector('.btn-nav-cta');
    if (cta) {
      cta.href = 'auth.html?view=login';
      cta.setAttribute('data-i', 'nav_login');
      cta.textContent = t.nav_login;
      cta.style.display = '';
    }
  }
}

/* ── Scroll-reveal ──────────────────────────────────────────── */
function rpInitReveal() {
  const els = document.querySelectorAll('[data-reveal]');
  if (!('IntersectionObserver' in window)) {
    els.forEach(el => el.classList.add('in-view'));
    return;
  }
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('in-view');
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  els.forEach(el => obs.observe(el));
}

/* ── Animated counters ──────────────────────────────────────── */
function rpAnimateCounters() {
  const counters = document.querySelectorAll('[data-count]');
  if (!counters.length) return;
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const target = parseInt(el.getAttribute('data-count'));
        const suffix = el.getAttribute('data-suffix') || '';
        const prefix = el.getAttribute('data-prefix') || '';
        const duration = 1500;
        const start = performance.now();
        el.classList.add('counting');
        function tick(now) {
          const elapsed = now - start;
          const progress = Math.min(elapsed / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          el.textContent = prefix + Math.round(target * eased).toLocaleString('ru-RU') + suffix;
          if (progress < 1) requestAnimationFrame(tick);
          else el.classList.remove('counting');
        }
        requestAnimationFrame(tick);
        obs.unobserve(el);
      }
    });
  }, { threshold: 0.3 });
  counters.forEach(el => obs.observe(el));
}

/* ── Navbar scroll effect ───────────────────────────────────── */
function rpInitScrollNav() {
  const nav = document.querySelector('nav');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 20);
  }, { passive: true });
}

/* ── Mobile nav toggle ──────────────────────────────────────── */
function rpToggleMobileNav() {
  const links = document.getElementById('navLinks');
  if (links) links.classList.toggle('mobile-open');
}

/* ── Hero particles ─────────────────────────────────────────── */
function rpInitParticles(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let particles = [];
  const count = 40;

  function resize() {
    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = canvas.parentElement.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2.5 + 0.5,
      dx: (Math.random() - 0.5) * 0.4,
      dy: (Math.random() - 0.5) * 0.4,
      opacity: Math.random() * 0.4 + 0.1,
    });
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
      p.x += p.dx;
      p.y += p.dy;
      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(37, 99, 235, ${p.opacity})`;
      ctx.fill();
    });
    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = `rgba(37, 99, 235, ${0.06 * (1 - dist / 120)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();
}

document.addEventListener('DOMContentLoaded', () => {
  rpApplyTranslations();
  rpInitReveal();
  rpAnimateCounters();
  rpInitScrollNav();
});
