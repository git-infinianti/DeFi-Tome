from django.shortcuts import render

# Create your views here.
def docs(request):
    """API Documentation page with DeFi-related commands"""
    return render(request, 'api/docs.html')
