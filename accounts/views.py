from django.shortcuts import render


def pending_approval(request):
    return render(request, "accounts/pending_approval.html")


def account_suspended(request):
    return render(request, "accounts/account_suspended.html")