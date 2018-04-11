# Copyright (c) 2018, Andrea Corbellini
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Perfect Storm Project.

from ..exceptions import ValidationError


class Field:

    def __init__(self, *, read_only=False, null=False, default=None):
        self.read_only = read_only
        self.null = null
        self.default = default

    def __set_name__(self, owner, name):
        self.name = name
        owner._fields.append(name)

    def embed(self, parent, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            # This field is being accessed from the model class
            return self

        # Field accessed from a model instance
        value = instance._data.get(self.name)
        if value is None:
            if callable(self.default):
                value = self.default()
            else:
                value = self.default
            instance._data[self.name] = value
        return value

    def __set__(self, instance, value):
        instance._data[self.name] = value

    def validate(self, value):
        if value is None and not self.null:
            raise ValidationError('field cannot be None', field=self.name)


class StringField(Field):

    def __init__(self, *args, blank=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.blank = blank

    def validate(self, value):
        super().validate(value)
        if value is None:
            return
        if not isinstance(value, str):
            raise ValidationError('expected a string, got {!r}'.format(value), field=self.name)
        if not value and not self.blank:
            raise ValidationError('field cannot be blank', field=self.name)


class IntField(Field):

    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, int):
            raise ValidationError('expected an integer, got {!r}'.format(value), field=self.name)


class ListField(Field):

    def __init__(self, subfield, **kwargs):
        kwargs.setdefault('default', list)
        super().__init__(**kwargs)
        self.subfield = subfield

    def __set_name__(self, owner, name):
        super().__set_name__(owner, name)
        self.subfield.embed(self, name + '.[]')

    def embed(self, parent, name):
        super().embed(parent, name)
        self.subfield.embed(self, name + '.[]')

    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, (tuple, list)):
                raise ValidationError('expected a list or tuple, got {!r}'.format(value), field=self.name)
            for item in value:
                self.subfield.validate(item)


class DictField(Field):

    def __init__(self, **kwargs):
        kwargs.setdefault('default', dict)
        super().__init__(**kwargs)

    def validate(self, value):
        super().validate(value)

        if value is not None and not isinstance(value, dict):
            raise ValidationError('expected a dict, got {!r}'.format(value), field=self.name)

        visited = set()

        def validate_inner(obj):
            if obj is None or isinstance(obj, (str, int, float)):
                return
            if id(obj) in visited:
                raise ValidationError('object has circular references', field=self.name)
            visited.add(id(obj))
            if isinstance(obj, (tuple, list)):
                for item in obj:
                    validate_inner(item)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    if not isinstance(key, str):
                        raise ValidationError('dictionary keys must be strings, found {!r}'.format(key), field=self.name)
                    validate_inner(value)
            else:
                raise ValidationError('unknown type: {!r}'.format(obj), field=self.name)
            visited.remove(id(obj))

        validate_inner(value)
