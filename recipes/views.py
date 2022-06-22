from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated

from backend.authentication import BearerTokenAuthentication
from recipes import models
from recipes import serializers


class RecipeCursorPagination(CursorPagination):
    cursor_query_param = 'pub_date'
    ordering = '-pub_date'


class RecipeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Recipe.objects.all()
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RecipeSerializer
    pagination_class = RecipeCursorPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        'pub_date': ['exact', 'lt', 'lte', 'gt', 'gte'],
        'rating': ['lt', 'lte', 'gt', 'gte'],
        'reviews_count': ['lt', 'lte', 'gt', 'gte'],
        'wma_count': ['lt', 'lte', 'gt', 'gte'],
        'tags': ['exact'],
        'authors': ['exact'],
    }
    ordering_fields = ['pub_date', 'reviews_count']
    ordering = ['-pub_date']
