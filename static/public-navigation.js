// Native anchors/history remain intact; offset follows wrapped nav and auth changes.
(() => {
  const header = document.querySelector('.public-header');
  if (!header) return;
  const update = () => {
    document.documentElement.style.setProperty('--public-header-height', `${Math.ceil(header.getBoundingClientRect().height)}px`);
  };
  update();
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(update).observe(header);
  window.addEventListener('resize', update, {passive:true});
})();
