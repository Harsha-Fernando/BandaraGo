from django.shortcuts import get_object_or_404, render

from .models import Category, Place


def place_list(request):
    categories = Category.objects.all()
    selected = request.GET.get('category', '')
    places = Place.objects.published().with_details()
    if selected:
        places = places.filter(categories__slug=selected)
    places = list(places)
    hero_place = next((place for place in places if place.slug == 'bolgoda-lake'), places[0] if places else None)
    return render(request, 'attractions/place_list.html', {
        'places': places, 'categories': categories, 'selected_category': selected,
        'is_home': request.path == '/', 'hero_place': hero_place,
    })


def place_detail(request, slug):
    place = get_object_or_404(Place.objects.published().with_details(), slug=slug)
    return render(request, 'attractions/place_detail.html', {
        'place': place,
        'photos': sorted(place.images.all(), key=lambda photo: not photo.is_cover),
        'more_places': Place.objects.published().with_details().exclude(pk=place.pk)[:4],
        'map_places': [{'name': place.name, 'latitude': float(place.latitude), 'longitude': float(place.longitude)}],
    })
