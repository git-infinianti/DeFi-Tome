from django.shortcuts import render

# Create your views here.
def register(request):
    return render(request, 'register/index.html')
def login(request):
    return render(request, 'login/index.html')
def home(request):
    return render(request, 'home/index.html')