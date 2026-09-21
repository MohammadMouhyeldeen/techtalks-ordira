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

  /* ---------- Variant selection (color -> size -> price/stock) ---------- */
  const swatches = Array.from(document.querySelectorAll('#colorSwatches .variant-swatch'));
  const pills = Array.from(document.querySelectorAll('#sizePills .pill'));
  const priceEl = document.getElementById('productPrice');
  const stockPill = document.getElementById('stockPill');
  const stockPillText = document.getElementById('stockPillText');
  const qtyStepper = document.getElementById('qtyStepper');
  const qtyValueEl = document.getElementById('qtyValue');
  const qtyMinus = document.getElementById('qtyMinus');
  const qtyPlus = document.getElementById('qtyPlus');
  const qtyStockNote = document.getElementById('qtyStockNote');
  const addToCartBtn = document.getElementById('addToCartBtn');

  let qty = 1;
  let currentStock = 0;
  let addedToCart = false;

  const setStockPill = (stock) => {
    if (!stockPill || !stockPillText) return;
    stockPill.classList.remove('is-low', 'is-out');
    if (stock <= 0) {
      stockPill.classList.add('is-out');
      stockPillText.textContent = 'Out of stock';
    } else if (stock <= 3) {
      stockPill.classList.add('is-low');
      stockPillText.textContent = `Only ${stock} left`;
    } else {
      stockPillText.textContent = 'In stock';
    }
  };

  const setQty = (value) => {
    const max = Math.max(currentStock, 0);
    qty = max === 0 ? 0 : Math.min(Math.max(value, 1), max);
    if (qtyValueEl) qtyValueEl.textContent = String(qty || 1);
    if (qtyMinus) qtyMinus.disabled = qty <= 1 || max === 0;
    if (qtyPlus) qtyPlus.disabled = qty >= max;
    qtyStepper?.classList.toggle('is-disabled', max === 0);
  };

  const activatePill = (pill) => {
    pills.forEach((p) => p.classList.toggle('active', p === pill));
    const price = pill?.dataset.price;
    currentStock = Number(pill?.dataset.stock || 0);

    if (priceEl && price) priceEl.textContent = `$${price}`;
    setStockPill(currentStock);
    setQty(1);

    if (qtyStockNote) {
      qtyStockNote.textContent = currentStock > 0 ? `${currentStock} available` : 'Unavailable in this size';
    }
    if (addToCartBtn && !addedToCart) addToCartBtn.disabled = currentStock <= 0;
  };

  const selectColor = (colorName) => {
    swatches.forEach((s) => s.classList.toggle('active', s.dataset.color === colorName));

    let firstVisibleEnabled = null;
    pills.forEach((pill) => {
      const matches = pill.dataset.color === colorName;
      pill.hidden = !matches;
      if (matches && !pill.disabled && !firstVisibleEnabled) firstVisibleEnabled = pill;
    });

    activatePill(firstVisibleEnabled || pills.find((p) => p.dataset.color === colorName));
  };

  swatches.forEach((swatch) => {
    swatch.addEventListener('click', () => selectColor(swatch.dataset.color));
  });

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      if (pill.disabled) return;
      activatePill(pill);
    });
  });

  qtyMinus?.addEventListener('click', () => setQty(qty - 1));
  qtyPlus?.addEventListener('click', () => setQty(qty + 1));

  const initialColor = swatches.find((s) => s.classList.contains('active'))?.dataset.color;
  if (initialColor) {
    selectColor(initialColor);
  } else {
    const activePill = pills.find((p) => p.classList.contains('active')) || pills[0];
    if (activePill) activatePill(activePill);
  }

  /* ---------- Add to cart ----------
     KNOWN LIMITATION (by design, for this sprint): this is cosmetic-only
     feedback (button state + toast), not a real cart. There is no Cart
     model, no session/localStorage persistence, and no shared state with
     catalog.js's quick-add buttons or a navbar cart icon (none exists yet).
     Refreshing this page or navigating away loses the "added" state.
     A real cart needs its own design pass (guest session cart vs
     localStorage vs requiring login, a navbar badge, etc.) rather than
     being improvised here. */
  const toast = document.getElementById('cartToast');
  const toastText = document.getElementById('cartToastText');
  let toastTimer = null;

  const showToast = (message) => {
    if (!toast) return;
    if (toastText) toastText.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2400);
  };

  addToCartBtn?.addEventListener('click', () => {
    if (addToCartBtn.disabled || currentStock <= 0 || addedToCart) return;

    const productName = document.querySelector('.product-detail__name')?.textContent.trim() || 'Item';
    const label = addToCartBtn.querySelector('span');

    addedToCart = true;
    addToCartBtn.classList.add('is-added');
    addToCartBtn.disabled = true;
    if (label) label.textContent = 'Added to Cart';
    showToast(`Added ${qty} × ${productName} to cart`);
  });

  /* ---------- Quick add-to-cart on related product cards ---------- */
  document.querySelectorAll('.related .product-card__add').forEach((btn) => {
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
