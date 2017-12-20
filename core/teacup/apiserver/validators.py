from django.core.exceptions import ValidationError


def validate_dict(value):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError('Value must be a JSON object')


def validate_list_of_strings(value):
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError('Value must be a JSON array of strings')
