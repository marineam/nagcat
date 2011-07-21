from django import template

register = template.Library()

state_names = {0: 'OK', 1: 'Warning', 2: 'Critical', 3: 'Unknown'}


@register.filter
def state_name(value):
    """Turn a nagio state number into a state name."""
    return state_names[int(value)]


def pluralize(count, word, alt=''):
    if not alt:
        alt = word + 's'

    return word if count == 1 else alt


@register.filter
def pretty_duration(dur, type='short'):
    dur = int(dur)

    if dur < 60:
        dur = round(dur)
        return "{0:.0f} {1}".format(dur, pluralize(dur, 'second'))

    dur /= 60.0
    if dur < 60:
        dur = round(dur)
        return "{0:.0f} {1}".format(dur, pluralize(dur, 'minute'))

    dur /= 60.0
    if dur < 24:
        dur = round(dur)
        return "{0:.0f} {1}".format(dur, pluralize(dur, 'hour'))

    dur /= 24.0
    dur = round(dur)
    return "{0:.0f} {1}".format(dur, pluralize(dur, 'day'))

