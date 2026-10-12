(() => {
  'use strict';

  const toast = document.getElementById('cartToast');
  const toastText = document.getElementById('cartToastText');
  let toastTimer = null;

  window.showStorefrontToast = (message, duration = 2800) => {
    if (!toast) return;
    if (toastText) toastText.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), duration);
  };

  if (toast?.dataset.flashMessage) {
    window.showStorefrontToast(toast.dataset.flashMessage);
  }
})();
