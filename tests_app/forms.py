from django import forms
from .models import Test, StudentGroup, TestCategory


class TestForm(forms.ModelForm):
    assigned_groups = forms.ModelMultipleChoiceField(
        queryset=StudentGroup.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Группы',
    )

    class Meta:
        model = Test

        fields = [
            'title',
            'description',
            'category',
            'time_limit',
            'max_attempts',
            'available_from',
            'available_until',
            'visibility',
            'assigned_groups',
            'shuffle_questions',
            'shuffle_answers',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название теста'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание теста'
            }),

            'category': forms.Select(attrs={
                'class': 'form-select',
            }),

            'time_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Например: 80'
            }),

            'max_attempts': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': '0 — без ограничений'
            }),

            'available_from': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }, format='%Y-%m-%dT%H:%M'),

            'available_until': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }, format='%Y-%m-%dT%H:%M'),

            'visibility': forms.Select(attrs={
                'class': 'form-select',
            }),

            'shuffle_questions': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),

            'shuffle_answers': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

        labels = {
            'title': 'Название теста',
            'description': 'Описание',
            'category': 'Категория / предмет',
            'time_limit': 'Время на тест, минут',
            'max_attempts': 'Количество попыток',
            'available_from': 'Доступен с',
            'available_until': 'Доступен до',
            'visibility': 'Кому доступен тест',
            'shuffle_questions': 'Перемешивать вопросы при прохождении',
            'shuffle_answers': 'Перемешивать варианты ответов',
        }

        help_texts = {
            'available_from': 'Если оставить пустым, тест будет доступен сразу после публикации.',
            'available_until': 'Если оставить пустым, тест не будет иметь даты окончания.',
            'assigned_groups': 'Используется, если выбрана видимость только для групп.',
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['available_from'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['available_until'].input_formats = ['%Y-%m-%dT%H:%M']

        if teacher is not None:
            self.fields['assigned_groups'].queryset = StudentGroup.objects.filter(
                created_by=teacher
            ).order_by('name')

        if self.instance and self.instance.pk:
            if self.instance.available_from:
                self.initial['available_from'] = self.instance.available_from.strftime('%Y-%m-%dT%H:%M')

            if self.instance.available_until:
                self.initial['available_until'] = self.instance.available_until.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()

        available_from = cleaned_data.get('available_from')
        available_until = cleaned_data.get('available_until')
        visibility = cleaned_data.get('visibility')
        assigned_groups = cleaned_data.get('assigned_groups')

        if available_from and available_until:
            if available_until <= available_from:
                raise forms.ValidationError(
                    'Дата окончания доступности должна быть позже даты начала.'
                )

        if visibility == 'groups' and not assigned_groups:
            raise forms.ValidationError(
                'Выберите хотя бы одну группу или установите видимость «Для всех студентов».'
            )

        return cleaned_data


class StudentGroupForm(forms.ModelForm):
    class Meta:
        model = StudentGroup
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: ИС-21-1',
            }),
        }
        labels = {
            'name': 'Название группы',
        }
