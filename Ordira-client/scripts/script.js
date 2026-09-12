(() => {
  'use strict';

  /* ---------- Header scroll state ---------- */
  const header = document.getElementById('siteHeader');
  const backToTop = document.getElementById('backToTop');

  const onScroll = () => {
    const scrolled = window.scrollY > 8;
    header?.classList.toggle('is-scrolled', scrolled);
    backToTop?.classList.toggle('is-visible', window.scrollY > 600);
  };
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  backToTop?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  /* ---------- Mobile nav ---------- */
  const navToggle = document.getElementById('navToggle');
  const mobileNav = document.getElementById('mobileNav');

  const closeMobileNav = () => {
    navToggle?.setAttribute('aria-expanded', 'false');
    mobileNav?.classList.remove('is-open');
  };

  navToggle?.addEventListener('click', () => {
    const isOpen = navToggle.getAttribute('aria-expanded') === 'true';
    navToggle.setAttribute('aria-expanded', String(!isOpen));
    mobileNav?.classList.toggle('is-open', !isOpen);
  });

  mobileNav?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', closeMobileNav);
  });

  /* ---------- Scroll reveal ---------- */
  const revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && revealEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add('is-visible'));
  }

  /* ---------- Hero stat counters ---------- */
  const counters = document.querySelectorAll('[data-count]');
  const animateCount = (el) => {
    const target = parseInt(el.getAttribute('data-count'), 10) || 0;
    const suffix = el.getAttribute('data-suffix') || '';
    const prefix = el.getAttribute('data-prefix') || '';
    const duration = 1100;
    const start = performance.now();

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = Math.round(target * eased);
      el.textContent = prefix + value + suffix;
      if (progress < 1) requestAnimationFrame(tick);
      else el.textContent = prefix + target + suffix;
    };
    requestAnimationFrame(tick);
  };

  if (counters.length) {
    if ('IntersectionObserver' in window) {
      const counterIO = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            animateCount(entry.target);
            counterIO.unobserve(entry.target);
          }
        });
      }, { threshold: 0.5 });
      counters.forEach((c) => counterIO.observe(c));
    } else {
      counters.forEach(animateCount);
    }
  }

  /* ---------- Shop link phone demo tabs ---------- */
  const demoTabs = document.querySelectorAll('.demo-tab');
  const demoPanels = document.querySelectorAll('.demo-panel');

  demoTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');

      demoTabs.forEach((t) => {
        t.classList.toggle('active', t === tab);
        t.setAttribute('aria-selected', String(t === tab));
      });

      demoPanels.forEach((panel) => {
        panel.classList.toggle('active', panel.getAttribute('data-panel') === target);
      });
    });
  });

  /* ---------- Pricing billing toggle ---------- */
  const billingSwitch = document.getElementById('billingSwitch');
  const billingLabels = document.querySelectorAll('.billing-label');
  const priceAmounts = document.querySelectorAll('.price-amount .amount');
  const periodEls = document.querySelectorAll('.price-amount .period');

  const setBilling = (annual) => {
    billingSwitch?.setAttribute('aria-checked', String(annual));
    billingLabels.forEach((label) => {
      const isAnnual = label.getAttribute('data-billing') === 'annual';
      label.classList.toggle('active', isAnnual === annual);
    });
    priceAmounts.forEach((amountEl) => {
      const value = annual ? amountEl.getAttribute('data-annual') : amountEl.getAttribute('data-monthly');
      amountEl.style.opacity = '0';
      setTimeout(() => {
        amountEl.textContent = value;
        amountEl.style.opacity = '1';
      }, 120);
    });
    periodEls.forEach((p) => { p.textContent = annual ? '/mo, billed yearly' : '/mo'; });
  };

  billingSwitch?.addEventListener('click', () => {
    const isAnnual = billingSwitch.getAttribute('aria-checked') === 'true';
    setBilling(!isAnnual);
  });

  billingLabels.forEach((label) => {
    label.addEventListener('click', () => setBilling(label.getAttribute('data-billing') === 'annual'));
  });

  /* ---------- FAQ accordion ---------- */
  const faqQuestions = document.querySelectorAll('.faq-question');

  const setFaqState = (button, open) => {
    const answer = button.nextElementSibling;
    button.setAttribute('aria-expanded', String(open));
    answer.style.maxHeight = open ? '480px' : '0px';
  };

  faqQuestions.forEach((button, index) => {
    setFaqState(button, index === 0);

    button.addEventListener('click', () => {
      const isOpen = button.getAttribute('aria-expanded') === 'true';
      faqQuestions.forEach((b) => setFaqState(b, false));
      setFaqState(button, !isOpen);
    });
  });

  /* ---------- Footer year ---------- */
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

})();
