from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    notifications = (
        Notification.objects
        .filter(recipient=request.user)
        .select_related("shop", "order")
        .order_by("-created_at")
    )

    return render(
        request,
        "notifications/notification_list.html",
        {
            "notifications": notifications,
        },
    )


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)

    return redirect("notifications:list")