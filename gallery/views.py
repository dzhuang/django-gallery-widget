import os
import json
from PIL import Image
from io import BytesIO
from urllib.parse import unquote

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.translation import gettext
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Case, Value, When, IntegerField
from django.core.exceptions import PermissionDenied, BadRequest
from django.urls import reverse
from django.core.files.base import ContentFile

from sorl.thumbnail import get_thumbnail
from gallery.models import BuiltInGalleryImage
from gallery import conf


def get_serialized_image(instance, image_field_name="image",
                         preview_size=conf.DEFAULT_THUMBNAIL_SIZE):
    image = getattr(instance, image_field_name)

    return {
        'pk': instance.pk,
        'name': os.path.basename(image.path),
        'size': image.size,
        'url': image.url,
        'thumbnailUrl':
            get_thumbnail(
                image,
                "%sx%s" % (preview_size, preview_size),
                crop="center",
                quality=conf.DEFAULT_THUMBNAIL_QUALITY).url,
        'deleteUrl': "javascript:void(0)",

        # todo: not implemented
        'cropUrl': reverse(conf.DEFAULT_CROP_URL_NAME),
    }


def get_ordered_serialized_images(
        request, pks, image_model_class, image_field_name,
        user_field_name, preview_size):
    assert isinstance(pks, list)

    # Preserving the order of image using id__in=pks
    # https://stackoverflow.com/a/37146498/3437454
    cases = [When(id=x, then=Value(i)) for i, x in enumerate(pks)]
    case = Case(*cases, output_field=IntegerField())

    filter_kwargs = {"id__in": pks}
    if not request.user.is_superuser:
        filter_kwargs[user_field_name] = request.user

    queryset = image_model_class.objects.filter(**filter_kwargs)
    queryset = queryset.annotate(my_order=case).order_by('my_order')

    files = [get_serialized_image(instance, image_field_name, preview_size
                                  ) for instance in queryset]

    return files


def is_image(file_obj):
    # Verify and close the file
    try:
        Image.open(BytesIO(file_obj.read())).verify()
        return True
    except IOError:
        return False
    finally:
        file_obj.seek(0)


@require_POST
@login_required
def upload(request, *args, **kwargs):
    if not request.is_ajax():
        raise PermissionDenied(gettext('Only Ajax Post is allowed.'))

    file = request.FILES['files[]'] if request.FILES else None
    if not is_image(file):
        raise RuntimeError()

    preview_size = request.POST.get('preview_size', conf.DEFAULT_THUMBNAIL_SIZE)

    instance = BuiltInGalleryImage.objects.create(
        image=file,
        creator=request.user
    )

    return JsonResponse(
        {"files":
             [get_serialized_image(instance=instance,
                                   preview_size=preview_size)]},
        status=200)


@login_required
@require_GET
def fetch(request):
    if not request.is_ajax():
        raise PermissionDenied(gettext('Only Ajax Post is allowed.'))

    pks = request.GET.get("pks", None)
    if not pks:
        raise BadRequest()

    preview_size = request.GET.get('preview_size', conf.DEFAULT_THUMBNAIL_SIZE)

    pks = json.loads(unquote(pks))

    files = get_ordered_serialized_images(
        request, pks, image_model_class=BuiltInGalleryImage,
        image_field_name="image", user_field_name="creator",
        preview_size=preview_size
    )

    return JsonResponse(
        {"files": files}, status=200)


class CropImageError(Exception):
    pass


def get_cropped_file(request, pk, cropped_result, image_model_class,
                     image_field_name, user_field_name, preview_size):

    old_instance = get_object_or_404(image_model_class, pk=pk)

    try:
        x = int(float(cropped_result['x']))
        y = int(float(cropped_result['y']))
        width = int(float(cropped_result['width']))
        height = int(float(cropped_result['height']))
        rotate = int(float(cropped_result['rotate']))
    except KeyError:
        raise CropImageError(
            gettext('There are errors, please refresh the page '
                    'or try again later'))

    old_image = getattr(old_instance, image_field_name)

    try:
        new_image = Image.open(old_image.path)
    except IOError:
        raise CropImageError(
            gettext('There are errors，please re-upload the image'))

    image_format = new_image.format

    if rotate != 0:
        # or it will raise "AttributeError: 'NoneType' object has no attribute
        # 'mode' error in pillow 3.3.0
        new_image = new_image.rotate(-rotate, expand=True)

    box = (x, y, x+width, y+height)
    new_image = new_image.crop(box)

    if new_image.mode != "RGB":
        # for example, png images
        new_image = new_image.convert("RGB")

    new_image_io = BytesIO()
    new_image.save(new_image_io, format=image_format)

    new_instance = old_instance
    new_instance.pk = None
    setattr(new_instance, user_field_name, request.user)

    new_instance_image_field = getattr(new_instance, image_field_name)
    new_instance_image_field.save(
        name=os.path.basename(getattr(old_instance, image_field_name).name),
        content=ContentFile(new_image_io.getvalue()),
        save=False
    )
    new_instance.save()
    return get_serialized_image(
        new_instance, image_field_name=image_field_name, preview_size=preview_size)


@login_required
@require_POST
def crop(request, *args, **kwargs):
    if not request.is_ajax():
        raise PermissionDenied(gettext('Only Ajax Post is allowed.'))

    try:
        pk = request.POST["pk"]
        cropped_result = json.loads(request.POST.get("croppedResult"))
    except KeyError:
        return JsonResponse(
            {
                'message': gettext('Bad Request')
            },
            status=400)

    preview_size = request.POST.get('preview_size')

    image_model_class = BuiltInGalleryImage
    image_field_name = "image"
    user_field_name = "creator"

    try:
        file = get_cropped_file(
            request, pk, cropped_result, image_model_class,
            image_field_name, user_field_name, preview_size)
    except Exception as e:
        return JsonResponse({
            'message': "%(type_e)s: %(str_e)s" % {
                "type_e": type(e).__name__,
                "str_e": str(e)}},
            status=400)

    return JsonResponse(
        {
            "file": file,
            'message': gettext('Done!')
        },
        status=200)
