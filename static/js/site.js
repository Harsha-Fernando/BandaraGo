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
