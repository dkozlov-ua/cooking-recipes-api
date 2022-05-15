import dateparser
from celery.result import AsyncResult
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from backend.authentication import BearerTokenAuthentication
from recipes import models
from recipes import serializers
from recipes import tasks


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

    @staticmethod
    @action(detail=False, methods=['POST'])
    def scrape(request: Request) -> Response:
        if request.query_params.get('from_date'):
            from_date = dateparser.parse(request.query_params['from_date'])
        else:
            try:
                from_date = models.Recipe.objects.latest().pub_date
            except models.Recipe.DoesNotExist:
                from_date = None
        task: AsyncResult = tasks.update_recipes_bonappetit.delay(from_date)
        return Response({
            'task_id': task.id,
        })
