import base64
import imghdr
import uuid

from django.core.files.base import ContentFile
from django.utils import six
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для картинки для возможности загрузки в base64 формате."""

    def to_internal_value(self, data):
        if isinstance(data, six.string_types):
            if 'data:' in data and ';base64,' in data:
                header, data = data.split(';base64,')

            try:
                decoded_file = base64.b64decode(data)
            except TypeError:
                self.fail('invalid_image')

            file_name = str(uuid.uuid4())[:12]
            file_extension = imghdr.what(file_name, decoded_file)
            complete_file_name = f'{file_name}.{file_extension}'
            data = ContentFile(decoded_file, name=complete_file_name)

        return super(Base64ImageField, self).to_internal_value(data)
