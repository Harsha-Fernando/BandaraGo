from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.forms.models import BaseInlineFormSet
from .models import Place, PlaceImage


class PlaceAdminForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if data.get('is_published') and not data.get('categories'):
            self.add_error('categories', 'Choose at least one category before publishing.')
        return data


class PlaceImageForm(forms.ModelForm):
    class Meta:
        model = PlaceImage
        fields = '__all__'

    def _get_validation_exclusions(self):
        # The formset checks cover uniqueness against the final set, including deletions.
        return super()._get_validation_exclusions() | {'is_cover'}

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if isinstance(image, UploadedFile) and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Choose an image no larger than 5 MB.')
        return image


class PlaceImageFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        remaining = [form for form in self.forms if form.cleaned_data
                     and not form.cleaned_data.get('DELETE') and form.cleaned_data.get('image')]
        if self.instance.is_published and not remaining:
            raise forms.ValidationError('Keep at least one image before publishing, or save the attraction as a draft.')
        if sum(bool(form.cleaned_data.get('is_cover')) for form in remaining) > 1:
            raise forms.ValidationError('Choose at most one cover image per attraction.')
