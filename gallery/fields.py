from django.utils.deconstruct import deconstructible
from django.db import models
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django import forms
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.validators import BaseValidator
from django.db.models.query_utils import DeferredAttribute
from django.db.models import Case, Value, When, IntegerField

from gallery import conf, defaults as gallery_widget_defaults
from gallery.widgets import GalleryWidget
from gallery.utils import (
    get_or_check_image_field, apps, logger)


@deconstructible
class MaxNumberOfImageValidator(BaseValidator):
    message = ngettext_lazy(
        'Number of images exceeded, only %(limit_value)d allowed',
        'Number of images exceeded, only %(limit_value)d allowed',
        'limit_value')
    code = 'max_number_of_images'

    def compare(self, a, b):
        return a > b

    def clean(self, x):
        return len(x)


class GalleryDescriptor(DeferredAttribute):
    """
    Used django.db.models.fields.files.FileDescriptor as an example.
    """

    def __set__(self, instance, value):
        instance.__dict__[self.field.attname] = value

    def __get__(self, instance, cls=None):
        image_list = super().__get__(instance, cls)

        if (isinstance(image_list, list)
                and not isinstance(image_list, GalleryImageList)):
            attr = self.field.attr_class(instance, self.field, image_list)
            instance.__dict__[self.field.name] = attr

        return instance.__dict__[self.field.name]


class GalleryImageList(list):
    def __init__(self, instance, field, field_value):
        super().__init__(field_value)
        self._field = field
        self.instance = instance
        self._value = field_value

    @property
    def objects(self):
        model = apps.get_model(self._field.target_model)

        # Preserving the order of image using id__in=pks
        # https://stackoverflow.com/a/37146498/3437454
        cases = [When(id=x, then=Value(i)) for i, x in enumerate(self._value)]
        case = Case(*cases, output_field=IntegerField())
        filter_kwargs = {"id__in": self._value}
        queryset = model.objects.filter(**filter_kwargs)
        queryset = queryset.annotate(_order=case).order_by('_order')
        return queryset


class GalleryField(models.JSONField):
    """This is a model field which saves the id of images.

    :param target_model: A string in the form of ``app_label.model_name``,
           which can be loaded by :meth:`django.apps.get_model` (see 
           `Django docs <https://docs.djangoproject.com/en/dev/ref/applications/#django.apps.apps.get_model>`_),
           defaults to `None`. If `None`, ``gallery.BuiltInGalleryImage``,
           which can be overridden by 
           ``settings.DJANGO_GALLERY_WIDGET_CONFIG["default_target_image_model"]``,
           will be used.

    :type target_model: str, optional.

    A valid ``target_model`` need to meet one of the following 2 requirements:

    1. It has a :class:`django.db.models.ImageField` named `"image"` 

    2. It has a :class:`django.db.models.ImageField` which not named `"image"`
       but the field can be accessed by a classmethod named `"get_image_field"`,
       for example:

    .. code-block:: python
        
       class MyImage(models.Model):
            photo = models.ImageField(
                upload_to="my_images", storage=default_storage, verbose_name=_("Image"))
            creator = models.ForeignKey(
                    settings.AUTH_USER_MODEL, null=False, blank=False,
                            verbose_name=_('Creator'), on_delete=models.CASCADE)
            
            @classmethod
            def get_image_field(cls):
                return cls._meta.get_field("photo")

    """  # noqa

    attr_class = GalleryImageList
    descriptor_class = GalleryDescriptor

    def contribute_to_class(self, cls, name, private_only=False):
        super().contribute_to_class(cls, name, private_only)
        setattr(cls, self.attname, self.descriptor_class(self))

    def __init__(self, target_model=None, *args, **kwargs):
        self._init_target_model = self.target_model = target_model
        if target_model is None:
            self.target_model = conf.DEFAULT_TARGET_IMAGE_MODEL

        self.target_model_image_field = (
            self._get_image_field_or_test(is_checking=False))

        super().__init__(*args, **kwargs)

    def _get_image_field_or_test(self, is_checking=False):
        return get_or_check_image_field(
            target_app_model_str=self._init_target_model,
            check_id_prefix="gallery_field",
            obj=self, is_checking=is_checking,
            log_if_using_default_in_checks=True)

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        errors.extend(self._check_target_model())
        return errors

    def _check_target_model(self):
        return self._get_image_field_or_test(is_checking=True)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['target_model'] = self.target_model
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        _defaults = ({
            "required": True,

            # The following 2 are used to validate GalleryWidget params
            # see GalleryWidget.defaults_checks()
            "target_model": self.target_model,
            "model_field": str(self)
        })
        _defaults.update(kwargs)
        formfield = super().formfield(**{
            'form_class': GalleryFormField,
            **_defaults,
        })
        return formfield


class GalleryFormField(forms.JSONField):
    """The default formfield for :class:`gallery.fields.GalleryField`.

    :param max_number_of_images: Max allowed number of images, defaults
           to `None`, which means unlimited.
    :type max_number_of_images: int, optional.

    :param kwargs: Besides the kwargs from parent class, the following were added:

           * target_model: str, a valid target image model which can be loaded by
             ``apps.get_model``. When this field is used in the model form,
             it is auto configured by the model instance.

             However, if this field is used as a non-model form field, when
             not specified, it will use the built-in default target image
             model ``gallery.BuiltInGalleryImage``, which can be overridden by
             ``settings.DJANGO_GALLERY_WIDGET_CONFIG['default_target_image_model']``.

           * widget: if not specified, defaults to ``GalleryWidget`` with default
             values.


    .. note:: If `target_model` not specified when initializing, an info will
       be logged to the stdout, which can be turned off by adding
       ``gallery_form_field.I001`` in ``settings.SILENCED_SYSTEM_CHECKS``.

    """

    default_error_messages = {
        'required': _("The submitted file is empty."),
        'invalid': _("The submitted images are invalid."),
    }

    def __init__(self, max_number_of_images=None, **kwargs):

        # The following 2 are used to validate GalleryWidget params
        # see GalleryWidget.defaults_checks()
        self._image_model = kwargs.pop("target_model", None)
        image_model_not_configured = False
        if self._image_model is None:
            # This happens when the formfield is used in a Non-model form
            image_model_not_configured = True
            self._image_model = conf.DEFAULT_TARGET_IMAGE_MODEL

        # Make sure the model is valid target image model
        if (self._image_model
                != gallery_widget_defaults.DEFAULT_TARGET_IMAGE_MODEL
                or image_model_not_configured):
            errors = get_or_check_image_field(
                target_app_model_str=(
                    None if image_model_not_configured else self._image_model),
                check_id_prefix="gallery_form_field",
                obj=self, is_checking=True,
                log_if_using_default_in_checks=True)
            for error in errors:
                if error.is_serious():
                    raise ImproperlyConfigured(str(error))
                else:
                    if error.is_silenced():
                        continue
                    logger.info(str(error))

        self._widget_belongs_to = kwargs.pop("model_field", None) or str(self)

        self._max_number_of_images = max_number_of_images
        super().__init__(**kwargs)

    _widget = GalleryWidget

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, value):
        # Property and setter are used to make sure the attributes will
        # be passed to new widget instance when the widget instance
        # is changed.
        setattr(value, "max_number_of_images", self.max_number_of_images)
        setattr(value, "image_model", self._image_model)
        setattr(value, "widget_belongs_to", self._widget_belongs_to)

        # Re-initialize the widget
        value.is_localized = bool(self.localize)
        value.is_required = self.required
        extra_attrs = self.widget_attrs(value) or {}
        value.attrs.update(extra_attrs)
        self._widget = value

        if self.widget.upload_handler_url is None:
            if self._image_model == conf.DEFAULT_TARGET_IMAGE_MODEL:
                self.widget.upload_handler_url = (
                    conf.DEFAULT_UPLOAD_HANDLER_URL_NAME)
        if self._image_model == conf.DEFAULT_TARGET_IMAGE_MODEL:
            if (not self.widget.disable_fetch
                    and self.widget.fetch_request_url is None):
                self.widget.fetch_request_url = conf.DEFAULT_FETCH_URL_NAME
            if (not self.widget.disable_server_side_crop
                    and self.widget.crop_request_url is None):
                self.widget.crop_request_url = conf.DEFAULT_CROP_URL_NAME

        assert self.widget.max_number_of_images == self.max_number_of_images

    @property
    def max_number_of_images(self):
        return self._max_number_of_images

    @max_number_of_images.setter
    def max_number_of_images(self, value):
        if value is not None:
            if not str(value).isdigit():
                raise TypeError(
                    "'max_number_of_images' expects a positive integer, "
                    "got %s." % str(value))
            value = int(value)
        self._max_number_of_images = value
        self._widget.max_number_of_images = value

        if value:
            self.validators.append(
                MaxNumberOfImageValidator(int(value)))

    def widget_attrs(self, widget):
        # If BootStrap is loaded, "hiddeninput" is added by BootStrap.
        # However, we need that css class to check changes of the form,
        # so we added it manually.
        return {
            "class": " ".join(
                [conf.FILES_FIELD_CLASS_NAME, "hiddeninput"])
        }

    def to_python(self, value):
        converted = super().to_python(value)

        if converted in self.empty_values:
            return converted

        # Make sure the json is a list of pks
        if not isinstance(converted, list):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
                params={'value': converted},
            )

        for _pk in converted:
            if not str(_pk).isdigit():
                raise ValidationError(
                    self.error_messages['invalid'],
                    code='invalid',
                    params={'value': converted},
                )

        # Make sure all pks exists
        image_model = apps.get_model(self._image_model)
        if (image_model.objects.filter(
                pk__in=list(map(int, converted))).count()
                != len(converted)):
            converted_copy = converted[:]
            converted = []
            for pk in converted_copy:
                if image_model.objects.filter(pk=pk).count():
                    converted.append(pk)

        return converted
