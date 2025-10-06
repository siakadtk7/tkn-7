from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)



register = template.Library()

@register.filter
def dict_get(d, key):
    """Mengambil value dari dictionary dengan key"""
    return d.get(key, {})
