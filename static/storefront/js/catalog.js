(() => {
  'use strict';

  /* ---------- Header scroll state ---------- */
  const header = document.getElementById('storefrontHeader');
  const onScroll = () => header?.classList.toggle('is-scrolled', window.scrollY > 8);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

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
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add('is-visible'));
  }

  /* ---------- Search + category filtering ---------- */
  const searchInput = document.getElementById('catalogSearch');
  const clearBtn = document.getElementById('catalogSearchClear');
  const filterButtons = document.querySelectorAll('#catalogFilters .filter-chip');
  const cards = document.querySelectorAll('#catalogGrid .product-card');
  const emptyState = document.getElementById('catalogEmpty');

  let activeCategory = 'all';

  const applyFilters = () => {
    const query = (searchInput?.value || '').trim().toLowerCase();
    let visibleCount = 0;

    cards.forEach((card) => {
      const matchesCategory = activeCategory === 'all' || card.dataset.category === activeCategory;
      const matchesQuery = !query || card.dataset.name.includes(query);
      const visible = matchesCategory && matchesQuery;
      card.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    emptyState?.classList.toggle('is-visible', visibleCount === 0);
    clearBtn?.toggleAttribute('hidden', query.length === 0);
  };

  searchInput?.addEventListener('input', applyFilters);

  clearBtn?.addEventListener('click', () => {
    if (searchInput) searchInput.value = '';
    applyFilters();
    searchInput?.focus();
  });

  filterButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      activeCategory = btn.dataset.filter;
      filterButtons.forEach((b) => b.classList.toggle('active', b === btn));
      applyFilters();
    });
  });

  /* ---------- Quick add-to-cart from the grid ----------
     KNOWN LIMITATION (by design, for this sprint): cosmetic-only (icon
     pulse + toast), no real cart — see the matching note in
     product-detail.js. Not shared with that page's Add to Cart state. */
  const toast = document.getElementById('cartToast');
  const toastText = document.getElementById('cartToastText');
  let toastTimer = null;

  const showToast = (message) => {
    if (!toast) return;
    if (toastText) toastText.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2200);
  };

  document.querySelectorAll('.product-card__add').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      const card = btn.closest('.product-card');
      const name = card?.querySelector('.product-card__name')?.textContent.trim() || 'Item';
      btn.classList.remove('is-added');
      requestAnimationFrame(() => btn.classList.add('is-added'));
      showToast(`Added ${name} to cart`);
      setTimeout(() => btn.classList.remove('is-added'), 500);
    });
  });

})();
