from django import forms
from django.db import models
from django.forms import ValidationError
from django.test import TestCase
from django.test.utils import isolate_apps, override_settings

from gallery.fields import GalleryField, GalleryFormField

from demo.models import DemoGallery
from tests.factories import DemoGalleryFactory
from tests import factories


class DemoTestGalleryForm(forms.ModelForm):
    class Meta:
        model = DemoGallery
        fields = ["images"]


IMAGE_DATA = [{
    "url": "/media/images/abcd.jpg",
    "thumbnailUrl": "/media/cache/a6/ee/abcdefg.jpg",
    "name": "abcd.jpg", "size": "87700", "pk": 1,
    "deleteUrl": "javascript:void(0)"}]


class GalleryFieldTest(TestCase):
    def setUp(self) -> None:
        factories.UserFactory.reset_sequence()
        factories.BuiltInGalleryImageFactory.reset_sequence()
        factories.DemoGalleryFactory.reset_sequence()
        self.user = factories.UserFactory()
        super().setUp()

    def test_form_save(self):
        image = factories.BuiltInGalleryImageFactory(creator=self.user)
        form = DemoTestGalleryForm(
            data={"images": [image.pk]})
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(DemoGallery.objects.count(), 1)

    def test_form_add_images(self):
        instance = factories.DemoGalleryFactory.create(creator=self.user)
        image2 = factories.BuiltInGalleryImageFactory(creator=self.user)
        self.assertEqual(DemoGallery.objects.count(), 1)
        self.assertEqual(len(DemoGallery.objects.first().images), 1)

        form = DemoTestGalleryForm(
            data={"images": instance.images + [image2.pk]},
            instance=instance
        )
        self.assertTrue(form.is_valid())
        form.save()

        self.assertEqual(DemoGallery.objects.count(), 1)
        new_images = DemoGallery.objects.first().images
        self.assertEqual(len(new_images), 2)

    def test_form_change_images(self):
        instance = DemoGalleryFactory.create(creator=self.user)
        self.assertEqual(DemoGallery.objects.count(), 1)
        self.assertEqual(len(DemoGallery.objects.first().images), 1)
        image2 = factories.BuiltInGalleryImageFactory(creator=self.user)

        form = DemoTestGalleryForm(
            data={"images": [image2.pk]},
            instance=instance
        )
        self.assertTrue(form.is_valid())
        form.save()

        self.assertEqual(DemoGallery.objects.count(), 1)
        new_images = DemoGallery.objects.first().images
        self.assertEqual(len(new_images), 1)

    def test_form_save_null(self):
        form = DemoTestGalleryForm(
            data={"images": ''},
        )
        form.fields["images"].required = False

        self.assertTrue(form.is_valid())
        form.save()

        self.assertEqual(DemoGallery.objects.count(), 1)
        new_images = DemoGallery.objects.first().images
        self.assertIsNone(new_images)

    def test_form_replace_null(self):
        instance = DemoGalleryFactory.create(creator=self.user)
        self.assertEqual(DemoGallery.objects.count(), 1)
        self.assertEqual(len(DemoGallery.objects.first().images), 1)

        form = DemoTestGalleryForm(
            data={"images": ''},
            instance=instance
        )
        form.fields["images"].required = False

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertEqual(DemoGallery.objects.count(), 1)
        new_images = DemoGallery.objects.first().images
        self.assertIsNone(new_images)

    def test_form_invalid(self):
        instance = DemoGalleryFactory.create(creator=self.user)
        self.assertEqual(DemoGallery.objects.count(), 1)
        self.assertEqual(len(DemoGallery.objects.first().images), 1)

        form = DemoTestGalleryForm(
            data={"images": ''},
            instance=instance
        )
        form.fields["images"].required = True

        self.assertFalse(form.is_valid())


class GalleryFormFieldTest(TestCase):
    def setUp(self) -> None:
        factories.UserFactory.reset_sequence()
        factories.BuiltInGalleryImageFactory.reset_sequence()
        factories.DemoGalleryFactory.reset_sequence()
        self.user = factories.UserFactory()
        super().setUp()

    def test_gallery_form_field_clean_image_not_exist(self):
        field = GalleryFormField()
        form_data = [100]

        msg = "'The submitted file is empty.'"

        with self.assertRaisesMessage(ValidationError, msg):
            field.clean(form_data)

    def test_gallery_form_field_clean(self):
        image = factories.BuiltInGalleryImageFactory(creator=self.user)
        field = GalleryFormField()
        form_data = [image.pk]
        cleaned_data = field.clean(form_data)
        self.assertEqual(cleaned_data, form_data)

    def test_gallery_form_field_clean_null_required(self):
        field = GalleryFormField(required=True)
        inputs = [
            '',
            [],
        ]

        msg = "'The submitted file is empty.'"

        for data in inputs:
            with self.subTest(data=data):
                with self.assertRaisesMessage(ValidationError, msg):
                    field.clean(data)

    def test_gallery_form_field_clean_null_not_required(self):
        field = GalleryFormField(required=False)
        inputs = [
            '',
            None,
            'null',
            []
        ]

        for data in inputs:
            with self.subTest(data=data):
                self.assertIsNone(field.clean(data))

    def test_gallery_form_field_clean_invalid_image_json(self):
        inputs = ['invalid-image']
        msg = "The submitted images are invalid."

        for required in [True, False]:
            with self.subTest(required=required):
                field = GalleryFormField(required=required)
                with self.assertRaisesMessage(ValidationError, msg):
                    field.clean(inputs)

    def test_gallery_form_field_clean_not_null_not_list(self):
        input_str = 'invalid-image'
        msg = "The submitted images are invalid."

        for required in [True, False]:
            with self.subTest(required=required):
                field = GalleryFormField(required=required)
                with self.assertRaisesMessage(ValidationError, msg):
                    field.clean(input_str)

    def test_gallery_form_field_clean_disabled_invalid(self):
        field = GalleryFormField(disabled=True)
        input_str = 'invalid-image'
        msg = "The submitted images are invalid."

        with self.assertRaisesMessage(ValidationError, msg):
            field.clean(input_str)

    def test_gallery_form_field_assign_max_number_of_images(self):
        field = GalleryFormField(required=False)
        max_number_of_images_list = [
            0,
            "1",
            "123",
            1234,
            None
        ]

        for n in max_number_of_images_list:
            with self.subTest(max_number_of_images=n):
                field.max_number_of_images = n
                if n is not None:
                    self.assertEqual(field.max_number_of_images, int(n))
                    self.assertEqual(field.widget.max_number_of_images, int(n))
                else:
                    self.assertIsNone(field.max_number_of_images)
                    self.assertIsNone(field.widget.max_number_of_images)

    def test_gallery_form_field_assign_max_number_of_images_invalid(self):
        field = GalleryFormField(required=False)
        max_number_of_images_list = [
            -1,
            "-1",
            "abc",
            object,
        ]

        for n in max_number_of_images_list:
            with self.subTest(max_number_of_images=n):
                with self.assertRaises(TypeError):
                    field.max_number_of_images = n

    def test_gallery_form_field_clean_max_number_of_images_exceeded(self):
        field = GalleryFormField()
        n = 1
        field.max_number_of_images = n

        images = factories.BuiltInGalleryImageFactory.create_batch(
            size=2, creator=self.user)

        msg = "Number of images exceeded, only %i allowed" % n

        with self.assertRaisesMessage(ValidationError, msg):
            field.clean([images[0].pk, images[1].pk])

    def test_gallery_form_field_clean_max_number_of_images_not_exceeded(self):
        field = GalleryFormField()
        field.max_number_of_images = 1

        image = factories.BuiltInGalleryImageFactory(creator=self.user)

        self.assertEqual(field.clean([image.pk]), [image.pk])

    def test_gallery_form_field_clean_max_number_of_images_zero(self):
        # zero means not limited
        field = GalleryFormField()
        field.max_number_of_images = 0

        images = factories.BuiltInGalleryImageFactory.create_batch(
            size=2, creator=self.user)

        data = [images[0].pk, images[1].pk]

        cleaned_data = field.clean(data)
        self.assertEqual(cleaned_data, data)


class GalleryFieldCheckTest(TestCase):
    def test_field_checks_valid(self):

        class MyModel(models.Model):
            field = GalleryField(target_model="tests.FakeInvalidImageModel1")

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "gallery_field.E004")

    @isolate_apps("tests")
    def test_field_checks_use_default_target(self):

        class MyModel(models.Model):
            field = GalleryField()

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "gallery_field.I001")

    @isolate_apps("tests")
    def test_field_checks_use_invalid_target(self):

        class MyModel(models.Model):
            field = GalleryField(target_model="non-exist.model")

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "gallery_field.E002")

    @isolate_apps("tests")
    def test_field_checks_use_invalid_get_image_field_method(self):

        class MyModel(models.Model):
            field = GalleryField(target_model="tests.FakeInvalidImageModel5")

        model = MyModel()
        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "gallery_field.E003")

    @isolate_apps("tests")
    # Here we are not loading "demo", while use MyImageModel
    @override_settings(INSTALLED_APPS=['gallery', 'tests'])
    def test_field_checks_app_not_in_installed_apps(self):
        class MyModel(models.Model):
            field = GalleryField("demo.MyImageModel")

        # We want to make sure it won't raise error when initializing.
        model = MyModel()

        errors = model.check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "gallery_field.E002")
        self.assertIn("LookupError", errors[0].msg)
