from django.contrib import admin
from .forms import PlaceAdminForm, PlaceImageForm, PlaceImageFormSet
from .models import Category, Place, PlaceImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def has_delete_permission(self, request, obj=None):
        if obj and obj.places.filter(is_published=True).exists():
            return False
        return super().has_delete_permission(request, obj)


class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    form = PlaceImageForm
    formset = PlaceImageFormSet
    extra = 2


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    form = PlaceAdminForm
    list_display = ['name', 'distance_display', 'is_published', 'updated_at']
    list_filter = ['is_published', 'categories']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['categories']
    readonly_fields = ['distance_display']
    inlines = [PlaceImageInline]
    save_on_top = True

    @admin.display(description='Distance from Bandaragama')
    def distance_display(self, obj):
        if obj and obj.latitude is not None and obj.longitude is not None:
            return f'{obj.distance_km:.1f} km (straight-line)'
        return 'Enter coordinates to calculate distance.'

    def save_formset(self, request, form, formset, change):
        # Admin wraps saving in a transaction; clear old cover flags before a cover swap.
        formset.instance.images.filter(is_cover=True).update(is_cover=False)
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for image_form in formset.forms:
            if image_form.cleaned_data and not image_form.cleaned_data.get('DELETE'):
                image = image_form.instance
                if image.pk or image in instances:
                    image.save()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.validate_publication()


admin.site.site_header = 'BandaraGo administration'
admin.site.site_title = 'BandaraGo admin'
admin.site.index_title = 'Manage local attractions'
