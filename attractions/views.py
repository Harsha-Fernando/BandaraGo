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
    guidance, sources = [], []
    for paragraph in place.visitor_information.replace('\r\n', '\n').split('\n\n'):
        if paragraph.startswith(('Information:', 'Photo:', 'Opening hours source:')):
            sources.append(paragraph)
        elif paragraph.strip() not in {
            'Confirm current access, opening hours, and any admission charges before travelling.',
            'Confirm current access and any temporary restrictions locally before travelling.',
        }:
            guidance.append(paragraph)
    hours_note = place.opening_hours_note
    if hours_note == 'Opening hours not verified; confirm locally before travelling.':
        hours_note = ''
    return render(request, 'attractions/place_detail.html', {
        'place': place,
        'visitor_guidance': '\n\n'.join(guidance),
        'source_information': '\n\n'.join(sources),
        'hours_note': hours_note,
        'photos': sorted(place.images.all(), key=lambda photo: not photo.is_cover),
        'more_places': Place.objects.published().with_details().exclude(pk=place.pk)[:4],
        'map_places': [{'name': place.name, 'latitude': float(place.latitude), 'longitude': float(place.longitude)}],
    })
