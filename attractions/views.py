from django.shortcuts import render

from .models import Category, Place


def place_list(request):
    categories = Category.objects.all()
    selected = request.GET.get('category', '')
    places = Place.objects.published().with_details()
    if selected:
        places = places.filter(categories__slug=selected)
    return render(request, 'attractions/place_list.html', {
        'places': places, 'categories': categories, 'selected_category': selected,
        'is_home': request.path == '/',
    })
