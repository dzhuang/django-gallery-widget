import json
from django import forms
from django.forms.renderers import DjangoTemplates
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.core.exceptions import ImproperlyConfigured

from gallery.fields import GalleryFormField
from gallery.widgets import GalleryWidget
from gallery import conf
from gallery import defaults

from tests import factories
from tests.test_fields import DemoTestGalleryModelForm


class GalleryWidgetTest(SimpleTestCase):
    @staticmethod
    def _get_rendered_field_html(field, print_output=False):
        class Form(forms.Form):
            f = field

        haystack = str(Form()['f'])
        if print_output:
            print(haystack)
        return haystack

    def assertFieldRendersIn(self, field, needle, strict=False, print_output=False):
        haystack = self._get_rendered_field_html(field, print_output)
        assert_in = self.assertInHTML if not strict else self.assertIn
        assert_in(needle, haystack)

    def assertFieldRendersNotIn(self, field, needle, print_output=False):
        haystack = self._get_rendered_field_html(field, print_output)
        self.assertNotIn(needle, haystack)

    def test_widget(self):
        field = GalleryFormField()
        self.assertIsInstance(field.widget, GalleryWidget)

    def test_required_widget_render(self):
        f = GalleryFormField(required=True)

        self.assertFieldRendersIn(
            f, '<input type="hidden" name="f" value="null"'
               ' class="django-gallery-widget-files-field '
               ' hiddeninput" required id="id_f">')

        f = GalleryFormField(required=False)
        self.assertFieldRendersIn(
            f, '<input type="hidden" name="f" value="null"'
               ' class="django-gallery-widget-files-field '
               ' hiddeninput" id="id_f">')

    def _render_widget(self, widget, name, value, attrs=None, **kwargs):
        django_renderer = DjangoTemplates()
        print_output = kwargs.pop("print_output", False)
        output = widget.render(name, value, attrs=attrs,
                               renderer=django_renderer, **kwargs)
        if print_output:
            print(output)
        return output

    def check_in_html(self, widget, name, value, html, attrs=None,
                      strict=False, print_output=False, **kwargs):
        output = self._render_widget(widget, name, value, attrs=attrs, **kwargs)
        assert_in = self.assertIn if strict else self.assertInHTML

        if print_output:
            print(output)

        if isinstance(html, str):
            html = [html]
        for _html in html:
            assert_in(_html, output)

    def check_not_in_html(self, widget, name, value, html, attrs=None, **kwargs):
        output = self._render_widget(widget, name, value, attrs=attrs, **kwargs)
        if isinstance(html, str):
            html = [html]
        for _html in html:
            self.assertNotIn(_html, output)

    def test_gallery_widget_render(self):
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        image_data = [1]
        value = json.dumps(image_data)
        expected_result = (
            '<input type="hidden" name="image" value="[1]"')
        self.check_in_html(
            f.widget, "image", value, strict=True,  html=[expected_result])

    def test_gallery_widget_jquery_upload_options_max_number_of_files_overridden(self):  # noqa
        from random import randint
        max_number_of_file_ui_options_value = randint(1, 10)
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        f.widget = GalleryWidget(
            jquery_upload_ui_options={
                "maxNumberOfFiles": max_number_of_file_ui_options_value})
        setattr(f.widget, "max_number_of_images", None)
        self.check_not_in_html(f.widget, "image", '', html="maxNumberOfFiles")

        f.widget = GalleryWidget(
            jquery_upload_ui_options={
                "maxNumberOfFiles": max_number_of_file_ui_options_value})
        setattr(f.widget, "max_number_of_images", 0)
        self.check_not_in_html(f.widget, "image", '', html="maxNumberOfFiles")

        max_number_of_file = randint(1, 10)
        f.widget = GalleryWidget(
            jquery_upload_ui_options={"maxNumberOfFiles": 0})

        setattr(f.widget, "max_number_of_images", max_number_of_file)
        expected_string = "maxNumberOfFiles: %i" % max_number_of_file
        self.check_in_html(f.widget, "image", '', strict=True, html=expected_string)

    def test_gallery_widget_preview_size(self):
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        f.widget = GalleryWidget()
        expected_string = "previewMaxWidth: %i" % conf.DEFAULT_THUMBNAIL_SIZE
        self.check_in_html(f.widget, "image", '', strict=True, html=expected_string)

        f.widget = GalleryWidget(preview_size=130)
        expected_string = "previewMaxWidth: %i" % 130
        self.check_in_html(f.widget, "image", '', strict=True, html=expected_string)

    def test_gallery_widget_jquery_upload_options_None(self):
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        self.check_in_html(
            f.widget, "image", '', strict=True, html="disableImageResize")

        f.widget = GalleryWidget(
            jquery_upload_ui_options={"disableImageResize": None})
        self.check_not_in_html(f.widget, "image", '', html="disableImageResize")

    def test_gallery_widget_disabled(self):
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        f.widget = GalleryWidget()
        file_upload_button = (
            '<input type="file" class="django-gallery-image-input" '
            'id="%(field_name)s-files" multiple accept="image/*" '
            'data-action="%(upload_handler_url)s">'
            % {"field_name": "image",
               "upload_handler_url":
                   reverse(defaults.DEFAULT_UPLOAD_HANDLER_URL_NAME)}
        )
        self.check_in_html(
            f.widget, "image", '',
            html=[file_upload_button])

        f.widget.attrs["readonly"] = True
        self.check_not_in_html(
            f.widget, "image", '',
            # The css class of file input button
            html=["django-gallery-image-input"])

    def test_gallery_widget_upload_handler_url_none(self):
        f = GalleryFormField(target_model=defaults.DEFAULT_TARGET_IMAGE_MODEL)
        f.widget = GalleryWidget()
        file_upload_button = (
            '<input type="file" class="django-gallery-image-input" '
            'id="%(field_name)s-files" multiple accept="image/*" '
            'data-action="%(upload_handler_url)s">'
            % {"field_name": "image",
               "upload_handler_url":
                   reverse(defaults.DEFAULT_UPLOAD_HANDLER_URL_NAME)}
        )
        self.check_in_html(
            f.widget, "image", '',
            html=[file_upload_button])

        f.widget.upload_handler_url = None
        self.check_not_in_html(
            f.widget, "image", '',
            # The css class of file input button
            html=["django-gallery-image-input"])

    def test_disabled_widget_render(self):
        f = GalleryFormField()
        self.assertFieldRendersIn(
            f, 'django-gallery-image-input', strict=True)

        f = GalleryFormField(disabled=True)
        self.assertFieldRendersNotIn(f, 'django-gallery-image-input')

    def test_widget_render_conflict(self):
        # the target image model is not the default,
        # some of the urls are default urls
        field = GalleryFormField(target_model="tests.FakeValidImageModel")

        test_case = {
            "gallery_image_upload":
                {"upload_handler_url": "test_image_upload"},
            "gallery_image_crop":
                {"crop_request_url": "test_image_crop"},
            "gallery_images_fetch":
                {"fetch_request_url": "test_images_fetch"}
        }

        default_urls = {
            "upload_handler_url": "gallery_image_upload",
            "crop_request_url": "gallery_image_crop",
            "fetch_request_url": "gallery_images_fetch"
        }

        for default, kwargs in test_case.items():
            with self.subTest(default=default, url_kwargs=kwargs):
                test_kwargs = default_urls.copy()
                test_kwargs.update(kwargs)

                field.widget = GalleryWidget(**test_kwargs)
                with self.assertRaises(ImproperlyConfigured) as cm:
                    self._render_widget(field.widget, "field", "")

                self.assertIn(
                    'You need to write your own views for your image model',
                    cm.exception.args[0], cm.exception)
                self.assertNotIn(
                    default,
                    cm.exception.args[0]
                )

    def test_widget_disable_fetch_no_conflict(self):
        field = GalleryFormField(target_model="tests.FakeValidImageModel")

        kwargs = {
            "upload_handler_url": "test_image_upload",
            "crop_request_url": "gallery_image_crop",  # a conflict url
            "fetch_request_url": "test_images_fetch",
            "disable_server_side_crop": True
        }

        field.widget = GalleryWidget(**kwargs)
        self._render_widget(field.widget, "field", "")

    def test_widget_disable_server_side_crop_no_conflict(self):
        field = GalleryFormField(target_model="tests.FakeValidImageModel")

        kwargs = {
            "upload_handler_url": "test_image_upload",
            "crop_request_url": "test_image_crop",
            "fetch_request_url": "gallery_images_fetch",  # a conflict url
            "disable_fetch": True
        }

        field.widget = GalleryWidget(**kwargs)
        self._render_widget(field.widget, "field", "")

    def test_widget_no_conflict(self):
        # the target image model and all urls are not using the default,
        field = GalleryFormField(target_model="tests.FakeValidImageModel")

        kwargs = {
            "upload_handler_url": "test_image_upload",
            "crop_request_url": "test_image_crop",
            "fetch_request_url": "test_images_fetch"
        }

        field.widget = GalleryWidget(**kwargs)
        # No error thrown
        self._render_widget(field.widget, "field", "")

    def test_widget_invalid_url(self):
        # the target image model and all urls are not using the default,
        field = GalleryFormField(target_model="tests.FakeValidImageModel")

        kwargs = {
            "upload_handler_url": "test_image_upload",
            "crop_request_url": "test_image_crop",
            "fetch_request_url": "test_images_fetch"
        }

        invalid_url_name = "invalid-url-name"

        for k, v in kwargs.items():
            with self.subTest(key=k, value=v):
                test_kwargs = kwargs.copy()
                test_kwargs.update({k: invalid_url_name})

                field.widget = GalleryWidget(**test_kwargs)
                with self.assertRaises(ImproperlyConfigured) as cm:
                    self._render_widget(field.widget, "field", "")

                expected_error_str = (
                        "'%s' is invalid: %s is neither a valid url "
                        "nor a valid url name." % (k, invalid_url_name)
                )

                self.assertIn(
                    expected_error_str,
                    cm.exception.args[0], cm.exception)


class GalleryWidgetTestExtra(TestCase):
    # This test cases need db support
    def setUp(self) -> None:
        factories.UserFactory.reset_sequence()
        factories.BuiltInGalleryImageFactory.reset_sequence()
        factories.DemoGalleryFactory.reset_sequence()
        self.user = factories.UserFactory()
        super().setUp()

    def test_no_fetch_request_url(self):
        gallery_obj = factories.DemoGalleryFactory.create(
            creator=self.user, number_of_images=5, shuffle=True)
        pks = list(gallery_obj.images)

        form = DemoTestGalleryModelForm(instance=gallery_obj)

        rendered_js_content = "// fetching existing images"
        rendered_js_instance_data = "(%s)" % str(pks)
        self.assertIn(rendered_js_content, form.as_table())
        self.assertIn(rendered_js_instance_data, form.as_table())

        # now we set fetch_request_url=None to the widget
        form.fields["images"].widget.fetch_request_url = None

        self.assertNotIn(rendered_js_content, form.as_table())
        self.assertNotIn(rendered_js_instance_data, form.as_table())

    def test_no_crop_request_url(self):
        gallery_obj = factories.DemoGalleryFactory.create(
            creator=self.user, number_of_images=5, shuffle=True)

        form = DemoTestGalleryModelForm(instance=gallery_obj)

        # This data attribute only exists in Edit buttons
        rendered_button_data_toggle = 'data-toggle="modal"'
        self.assertIn(rendered_button_data_toggle, form.as_table())

        # # now we set crop_request_url=None to the widget
        form.fields["images"].widget.crop_request_url = None
        self.assertNotIn(rendered_button_data_toggle, form.as_table())
