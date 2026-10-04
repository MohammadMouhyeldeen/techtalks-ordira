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

})();
