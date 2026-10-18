from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from .distance import MAX_DISTANCE_KM, distance_from_bandaragama


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class PlaceQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, categories__isnull=False, images__isnull=False).distinct()

    def with_details(self):
        return self.prefetch_related('categories', 'images')


class Place(models.Model):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    categories = models.ManyToManyField(Category, related_name='places', blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    address = models.CharField(max_length=300, blank=True)
    opening_hours_note = models.CharField(max_length=300, blank=True)
    opening_hours = models.TextField(blank=True, help_text='Weekly visitor schedule, one day or day range per line. Include closed days and 24-hour listings where verified.')
    google_maps_query = models.CharField(max_length=300, blank=True, help_text='Named attraction and locality for Google Maps location links. Do not use a generic lake or beach point as an entrance.')
    google_maps_place_id = models.CharField(max_length=255, blank=True, help_text='Optional verified Google place ID to identify an exact listing rather than a search result.')
    google_maps_embed_url = models.URLField(max_length=2000, blank=True, help_text='Paste only the https://www.google.com/maps/embed?pb= URL from Google Maps Share > Embed a map, not the iframe HTML.')
    visitor_information = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlaceQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(condition=models.Q(latitude__gte=-90, latitude__lte=90), name='valid_latitude'),
            models.CheckConstraint(condition=models.Q(longitude__gte=-180, longitude__lte=180), name='valid_longitude'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.google_maps_embed_url:
            url = urlsplit(self.google_maps_embed_url)
            if url.scheme != 'https' or url.netloc != 'www.google.com' or url.path != '/maps/embed' or not url.query.startswith('pb='):
                raise ValidationError({'google_maps_embed_url': 'Use the HTTPS embed URL copied from Google Maps Share > Embed a map.'})
        if self.latitude is not None and self.longitude is not None:
            try:
                lat, lon = Decimal(self.latitude), Decimal(self.longitude)
            except (InvalidOperation, TypeError, ValueError):
                return  # Field validators report malformed coordinates.
            if lat.is_finite() and lon.is_finite() and -90 <= lat <= 90 and -180 <= lon <= 180:
                if self.distance_km > MAX_DISTANCE_KM:
                    raise ValidationError({'latitude': 'Attractions must be within 25 km of Bandaragama.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def validate_publication(self):
        """Call after saving category and image relationships in a publishing workflow."""
        if self.is_published and (not self.pk or not self.categories.exists() or not self.images.exists()):
            raise ValidationError('A published attraction needs at least one category and one image.')

    @property
    def map_url(self):
        query = self.google_maps_query or ', '.join(filter(None, [self.name, self.address, 'Sri Lanka']))
        parameters = {'api': 1, 'query': query}
        if self.google_maps_place_id:
            parameters['query_place_id'] = self.google_maps_place_id
        return 'https://www.google.com/maps/search/?' + urlencode(parameters)

    @property
    def distance_km(self):
        return distance_from_bandaragama(self.latitude, self.longitude)

    @property
    def cover_image(self):
        images = list(self.images.all())
        return next((image for image in images if image.is_cover), images[0] if images else None)

    def get_absolute_url(self):
        return reverse('attractions:detail', args=[self.slug])


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='places/%Y/%m/', validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])])
    alt_text = models.CharField(max_length=250, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_cover = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'pk']
        constraints = [models.UniqueConstraint(fields=['place'], condition=models.Q(is_cover=True), name='one_cover_per_place')]

    def __str__(self):
        return self.alt_text or f'Image for {self.place}'
