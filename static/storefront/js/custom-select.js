(() => {
  'use strict';

  /* Progressive enhancement: the real <select> stays in the DOM (still
     submits normally) but is visually hidden, replaced by an accessible
     button + listbox built from its own <option>s. Without JS the plain
     native <select> still works. */

  const enhance = (select) => {
    const wrap = select.closest('.select-wrap');
    if (!wrap || wrap.dataset.enhanced) return;
    wrap.dataset.enhanced = 'true';
    wrap.classList.add('custom-select');

    const iconId = wrap.dataset.icon;
    const nativeId = select.id;
    const triggerId = `${nativeId}-trigger`;
    const listId = `${nativeId}-listbox`;

    select.classList.add('custom-select__native');
    select.setAttribute('tabindex', '-1');
    select.setAttribute('aria-hidden', 'true');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.id = triggerId;
    trigger.className = 'custom-select__trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', listId);
    trigger.innerHTML =
      (iconId ? `<svg width="16" height="16" class="custom-select__trigger-icon"><use href="#${iconId}"/></svg>` : '') +
      '<span class="custom-select__value"></span>' +
      '<svg width="14" height="14" class="custom-select__chevron"><use href="#i-chevron-down"/></svg>';

    const list = document.createElement('ul');
    list.id = listId;
    list.className = 'custom-select__list';
    list.setAttribute('role', 'listbox');
    list.hidden = true;

    const options = Array.from(select.options).map((opt) => {
      const li = document.createElement('li');
      li.className = 'custom-select__option';
      li.setAttribute('role', 'option');
      li.dataset.value = opt.value;
      li.textContent = opt.textContent;
      li.setAttribute('aria-selected', opt.selected ? 'true' : 'false');
      list.appendChild(li);
      return li;
    });

    const valueEl = trigger.querySelector('.custom-select__value');
    const syncTriggerLabel = () => {
      const selected = select.options[select.selectedIndex];
      valueEl.textContent = selected ? selected.textContent : '';
    };
    syncTriggerLabel();

    wrap.appendChild(trigger);
    wrap.appendChild(list);

    const label = document.querySelector(`label[for="${nativeId}"]`);
    if (label) label.setAttribute('for', triggerId);

    let activeIndex = Math.max(options.findIndex((li) => li.getAttribute('aria-selected') === 'true'), 0);

    const highlight = (index) => {
      options.forEach((li, i) => li.classList.toggle('is-active', i === index));
      options[index]?.scrollIntoView({ block: 'nearest' });
    };

    const closeList = () => {
      wrap.classList.remove('is-open');
      list.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    };

    const openList = () => {
      wrap.classList.add('is-open');
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      highlight(activeIndex);
    };

    const selectOption = (index) => {
      const li = options[index];
      if (!li) return;
      select.value = li.dataset.value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      options.forEach((opt, i) => opt.setAttribute('aria-selected', i === index ? 'true' : 'false'));
      activeIndex = index;
      syncTriggerLabel();
      closeList();
      trigger.focus();
    };

    trigger.addEventListener('click', () => {
      if (wrap.classList.contains('is-open')) closeList();
      else openList();
    });

    options.forEach((li, index) => {
      li.addEventListener('click', () => selectOption(index));
      li.addEventListener('mouseenter', () => highlight(index));
    });

    trigger.addEventListener('keydown', (event) => {
      const isOpen = wrap.classList.contains('is-open');

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (!isOpen) { openList(); return; }
        activeIndex = Math.min(activeIndex + 1, options.length - 1);
        highlight(activeIndex);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (!isOpen) { openList(); return; }
        activeIndex = Math.max(activeIndex - 1, 0);
        highlight(activeIndex);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        if (isOpen) selectOption(activeIndex);
        else openList();
      } else if (event.key === 'Escape' && isOpen) {
        event.preventDefault();
        closeList();
      }
    });

    document.addEventListener('click', (event) => {
      if (!wrap.contains(event.target)) closeList();
    });
  };

  document.querySelectorAll('.select-wrap select.form-input').forEach(enhance);
})();
