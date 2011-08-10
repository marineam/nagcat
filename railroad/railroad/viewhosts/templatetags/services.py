from datetime import datetime, timedelta

from django import template
register = template.Library()


@register.filter
def state_name(value):
    """Turn a nagio state number into a state name."""
    state_names = {0: 'OK', 1: 'Warning', 2: 'Critical', 3: 'Unknown'}
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


def sameday(dt1, dt2):
    """Do two datetimes reference the same day? (ignore times)"""
    return (dt1.day == dt2.day and dt1.month == dt2.month
            and dt1.year == dt2.year)


@register.filter
def pretty_daterange(start, end):
    """Give a smart/pretty representation of a duration from start to end."""
    if sameday(start, end):
        fmt = "from {start_time} to {end_time} {end_day}"
    else:
        fmt = "From {start_time} {start_day} to {end_time} {end_day}"

    data = {
        'start_day': start.strftime('on %m/%d/%Y'),
        'start_time': start.strftime('%H:%M'),
        'end_day': end.strftime('on %m/%d/%Y'),
        'end_time': end.strftime('%H:%M'),
    }

    yesterday = datetime.now() + timedelta(days=-1)
    tomorrow = datetime.now() + timedelta(days=1)
    if sameday(start, yesterday):
        data['start_day'] = 'yesterday'
    elif sameday(start, datetime.now()):
        data['start_day'] = 'today'
    elif sameday(start, tomorrow):
        data['start_day'] = 'tomorrow'

    if sameday(end, yesterday):
        data['end_day'] = 'yesterday'
    elif sameday(end, datetime.now()):
        data['end_day'] = 'today'
    elif sameday(end, tomorrow):
        data['end_day'] = 'tomorrow'

    return fmt.format(**data)
