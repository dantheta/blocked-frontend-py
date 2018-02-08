import yaml
from flask import current_app

__all__ = ['load_country_data','load_isp_data','load_data']

def load_data(filename):
    with current_app.open_resource('data/'+filename+'.yml') as fp:
        return yaml.load(fp)

def load_country_data():
    return load_data('countries')

def load_isp_data():
    return load_data('isps')