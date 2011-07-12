from django import template

register = template.Library()

state_names = {0: 'OK', 1: 'Warning', 2: 'Critical', 3: 'Unknown'}


@register.filter
def state_name(value):
    """Turn a nagio state number into a state name."""
    return state_names[int(value)]
