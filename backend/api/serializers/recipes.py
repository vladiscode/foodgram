from operator import itemgetter

from rest_framework import serializers

from api.serializers.custom_fields import Base64ImageField
from api.serializers.tags import TagSerializer
from api.serializers.users import UserGetSerializer
from recipes.models import Recipe, IngredientInRecipe, Tag, Favorite, ShoppingCart


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для промежуточной модели IngredientInRecipe"""
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount',)
        extra_kwargs = {
            'id': {'required': True},
            'amount': {'required': True}
        }


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Recipe."""
    author = serializers.SerializerMethodField(read_only=True)
    ingredients = serializers.SerializerMethodField(read_only=True)
    tags = serializers.SerializerMethodField(read_only=True)
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def get_author(self, obj):
        request = self.context.get('request')
        context = {'request': request}
        return UserGetSerializer(obj.author, context=context).data

    def get_ingredients(self, obj):
        ingredients = IngredientInRecipe.objects.filter(recipe=obj)
        return IngredientInRecipeSerializer(ingredients, many=True).data

    def get_tags(self, obj):
        tags = Tag.objects.filter(recipes=obj)
        return TagSerializer(tags, many=True).data

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(user=request.user, recipe=obj.id).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if not request.user.is_authenticated:
            return False
        return ShoppingCart.objects.filter(user=request.user, recipe=obj.id).exists()


class RecipeCreateEditSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и изменения рецептов"""
    image = Base64ImageField(
        max_length=None, use_url=True,
    )
    ingredients = IngredientInRecipeSerializer(source="ingredient_amount", many=True)

    class Meta:
        model = Recipe
        fields = ('id', 'ingredients', 'tags', 'image', 'name', 'text', 'cooking_time')
        extra_kwargs = {
            'ingredients': {'required': True},
            'tags': {'required': True}
        }

    def validate(self, data):
        """
        Валидация входящих данных.
        :param data: данные
        :return: обновленные данные, содержащие автора и ингредиенты
        """
        data.pop('ingredient_amount')
        data.update({
            'author': self.context['request'].user,
            'ingredients': self.context['request'].data['ingredients']
        })
        return data

    @staticmethod
    def create_ingredients_in_recipe(recipe_id, ingredients):
        """
        Создание объектов промежуточной модели IngredientInRecipe.
        :param recipe_id: к какому рецепту создать
        :param ingredients: необходимые ингредиенты с количеством
        """
        for ingredient in ingredients:
            IngredientInRecipe.objects.create(
                ingredient_id=ingredient['id'],
                recipe_id=recipe_id,
                amount=ingredient['amount']
            )

    def create(self, validated_data):
        """
        Создание объекта рецепта с предварительным удалением рецептов из данных.
        :param validated_data: провалидированные данные
        :return: созданный объект рецепта
        """
        ingredients = validated_data.pop('ingredients')
        recipe = super().create(validated_data)
        self.create_ingredients_in_recipe(recipe.id, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """
        Редактирование рецепта
        Удаление и создание объектов промежуточной модели IngredientInRecipe происходит только в случае,
        если данные отличаются.
        :param instance: рецепт
        :param validated_data: провалидированные данные
        :return: отредактированный рецепт
        """
        new_ingredients = validated_data.pop('ingredients')
        recipe = super().update(instance, validated_data)
        old_ingredients_objects = IngredientInRecipe.objects.filter(recipe=instance.id)
        old_ingredients = [
            {
                'id': old_ingredient.ingredient_id,
                'amount': old_ingredient.amount
            } for old_ingredient in old_ingredients_objects
        ]
        if sorted(old_ingredients, key=itemgetter('id')) != sorted(new_ingredients, key=itemgetter('id')):
            old_ingredients_objects.delete()
            self.create_ingredients_in_recipe(instance.id, new_ingredients)
        return recipe

    def to_representation(self, instance):
        """
        Отображение данных рецепта через RecipeSerializer.
        :param instance: рецепт
        :return: сериализованные данные
        """
        request = self.context.get('request')
        context = {'request': request}
        return RecipeSerializer(instance, context=context).data


class RecipesShortInfo(serializers.ModelSerializer):
    """Сериализатор для отображения рецептов избранном, подписке и списке покупок."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time',)
