document.querySelectorAll('img').forEach((image) => {
  const showFallback = () => {
    const fallback = document.createElement('div');
    fallback.className = 'photo-empty rounded-2xl';
    fallback.textContent = 'Photograph unavailable';
    image.replaceWith(fallback);
  };
  image.addEventListener('error', showFallback, {once: true});
  if (image.complete && image.naturalWidth === 0) showFallback();
});
