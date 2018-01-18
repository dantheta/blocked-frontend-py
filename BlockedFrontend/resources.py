import yaml
from flask import current_app

__all__ = ['load_country_data']

def load_country_data():
    with current_app.open_resource('data/countries.yml') as fp:
        return yaml.load(fp)