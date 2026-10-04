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
  const variantIdInput = document.getElementById('variantIdInput');
  const quantityInput = document.getElementById('quantityInput');

  let qty = 1;
  let currentStock = 0;

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
    if (quantityInput) quantityInput.value = String(qty || 1);
    qtyStepper?.classList.toggle('is-disabled', max === 0);
  };

  const activatePill = (pill) => {
    pills.forEach((p) => p.classList.toggle('active', p === pill));
    const price = pill?.dataset.price;
    currentStock = Number(pill?.dataset.stock || 0);

    if (priceEl && price) priceEl.textContent = `$${price}`;
    if (variantIdInput) variantIdInput.value = pill?.dataset.variantId || '';
    setStockPill(currentStock);
    setQty(1);

    if (qtyStockNote) {
      qtyStockNote.textContent = currentStock > 0 ? `${currentStock} available` : 'Unavailable in this size';
    }
    if (addToCartBtn) addToCartBtn.disabled = currentStock <= 0;
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

})();
