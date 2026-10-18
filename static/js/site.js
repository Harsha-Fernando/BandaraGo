document.querySelectorAll('img').forEach((image) => {
  const showFallback = () => {
    const fallback = document.createElement('div');
    fallback.className = 'bg-light text-secondary text-center border rounded p-4';
    fallback.textContent = 'Photograph unavailable';
    image.replaceWith(fallback);
  };
  image.addEventListener('error', showFallback, {once: true});
  if (image.complete && image.naturalWidth === 0) showFallback();
});

// Only routine messages expire; errors and warnings remain available.
document.querySelectorAll('[data-auto-dismiss]').forEach((alert) => {
  let timer;
  const dismiss = () => {
    if (alert.contains(document.activeElement)) return;
    if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(alert).close();
    else alert.remove();
  };
  const schedule = () => { clearTimeout(timer); timer = setTimeout(dismiss, 5000); };
  alert.addEventListener('mouseenter', () => clearTimeout(timer));
  alert.addEventListener('mouseleave', schedule);
  alert.addEventListener('focusin', () => clearTimeout(timer));
  alert.addEventListener('focusout', schedule);
  schedule();
});
