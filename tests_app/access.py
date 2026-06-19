from django.db.models import Q


def student_can_access_test(user, test):
    if not test.is_active:
        return False

    if test.visibility == 'all':
        return True

    group = getattr(user.profile, 'student_group', None)
    if group is None:
        return False

    return test.assigned_groups.filter(id=group.id).exists()


def get_visible_tests_for_student(user, queryset=None):
    from .models import Test

    queryset = queryset or Test.objects.filter(is_active=True)

    group = getattr(user.profile, 'student_group', None)
    return queryset.filter(
        Q(visibility='all') |
        Q(visibility='groups', assigned_groups=group)
    ).distinct()
