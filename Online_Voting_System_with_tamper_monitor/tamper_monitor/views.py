from django.http import JsonResponse
from .models import TamperAlert
from django.views.decorators.http import require_GET
from django.contrib.admin.views.decorators import staff_member_required

@require_GET
@staff_member_required
def unacked_count(request):
    cnt = TamperAlert.objects.filter(acknowledged=False).count()
    return JsonResponse({'count': cnt})
