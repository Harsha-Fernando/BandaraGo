from django.contrib import messages
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from attractions.models import Place
from .pdf import build_plan_pdf

SESSION_KEY = 'visit_plan'


def plan_places(request):
    stored = request.session.get(SESSION_KEY, [])
    if not isinstance(stored, list):
        stored = []
    ids = list(dict.fromkeys(value for value in stored if type(value) is int and 0 < value < 2**63))
    places = Place.objects.published().with_details().filter(pk__in=ids).in_bulk()
    return [places[pk] for pk in ids if pk in places]


@require_GET
def plan_detail(request):
    return render(request, 'planner/plan.html', {'places': plan_places(request)})


@require_GET
def download_pdf(request):
    places = plan_places(request)
    if not places:
        messages.info(request, 'Add a place to your plan before downloading it.')
        return redirect('planner:detail')
    response = FileResponse(build_plan_pdf(places), as_attachment=True,
                            filename='bandarago-one-day-plan.pdf', content_type='application/pdf')
    response['Cache-Control'] = 'private, no-store'
    return response


@require_POST
def add(request, place_id):
    place = get_object_or_404(Place.objects.published(), pk=place_id)
    ids = [item.pk for item in plan_places(request)]
    if place.pk not in ids:
        ids.append(place.pk)
        messages.success(request, f'{place.name} added to your day.')
    else:
        messages.info(request, f'{place.name} is already in your plan.')
    request.session[SESSION_KEY] = ids
    return redirect('planner:detail')


@require_POST
def reorder(request, place_id):
    ids = [place.pk for place in plan_places(request)]
    direction = request.POST.get('direction')
    if place_id not in ids or direction not in ['up', 'down']:
        return HttpResponseBadRequest('Choose a place in your plan and a valid direction.')
    index = ids.index(place_id)
    destination = index + (-1 if direction == 'up' else 1)
    if 0 <= destination < len(ids):
        ids[index], ids[destination] = ids[destination], ids[index]
    request.session[SESSION_KEY] = ids
    return redirect('planner:detail')


@require_GET
def confirm_remove(request, place_id):
    place = get_object_or_404(Place.objects.published(), pk=place_id)
    return render(request, 'planner/confirm.html', {'place': place})


@require_POST
def remove(request, place_id):
    if request.POST.get('confirmed') != 'yes':
        return HttpResponseBadRequest('Confirm removal first.')
    request.session[SESSION_KEY] = [place.pk for place in plan_places(request) if place.pk != place_id]
    messages.success(request, 'Attraction removed from your plan.')
    return redirect('planner:detail')


@require_GET
def confirm_clear(request):
    return render(request, 'planner/confirm.html')


@require_POST
def clear(request):
    if request.POST.get('confirmed') != 'yes':
        return HttpResponseBadRequest('Confirm clearing first.')
    request.session[SESSION_KEY] = []
    messages.success(request, 'Your visit plan has been cleared.')
    return redirect('planner:detail')
