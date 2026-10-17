from .views import plan_places


def navigation(request):
    return {'plan_count': len(plan_places(request))}
